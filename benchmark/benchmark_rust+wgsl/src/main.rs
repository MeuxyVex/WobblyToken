use bytemuck::{Pod, Zeroable};
use std::{env, sync::mpsc, time::Instant};

const MAX_NONCE: u32 = u32::MAX;
const GPU_BATCH: u32 = 256 * 65_535;

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
struct Params {
    base_nonce: u32,
    difficulty: u32,
    count: u32,
    padding: u32,
}

async fn run_gpu(difficulty: u32) -> Result<(u32, u64, String, f64), String> {
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::all(),
        flags: wgpu::InstanceFlags::empty(),
        dx12_shader_compiler: wgpu::Dx12Compiler::Fxc,
        gles_minor_version: wgpu::Gles3MinorVersion::Automatic,
    });
    
    let adapter = instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        compatible_surface: None,
        force_fallback_adapter: false,
    }).await.ok_or("Aucun GPU compatible wgpu trouvé")?;
    
    let info = adapter.get_info();
    let device_name = format!("{} ({:?})", info.name, info.backend);
    
    let (device, queue) = adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("PoW device"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::downlevel_defaults(),
            memory_hints: Default::default(),
        },
        None,
    ).await.map_err(|error| error.to_string())?;

    let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: Some("SHA-256 PoW"),
        source: wgpu::ShaderSource::Wgsl(include_str!("shader.wgsl").into()),
    });
    
    let params_buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("params"),
        size: std::mem::size_of::<Params>() as u64,
        usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    });
    
    let result_buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("result"), size: 8,
        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    });
    
    let read_buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("readback"), size: 8,
        usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    });
    
    let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
        label: Some("layout"),
        entries: &[
            wgpu::BindGroupLayoutEntry {
                binding: 0, visibility: wgpu::ShaderStages::COMPUTE,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false, min_binding_size: None,
                }, count: None,
            },
            wgpu::BindGroupLayoutEntry {
                binding: 1, visibility: wgpu::ShaderStages::COMPUTE,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Storage { read_only: false },
                    has_dynamic_offset: false, min_binding_size: None,
                }, count: None,
            },
        ],
    });
    
    let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some("bind group"), layout: &layout,
        entries: &[
            wgpu::BindGroupEntry { binding: 0, resource: params_buffer.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 1, resource: result_buffer.as_entire_binding() },
        ],
    });
    
    let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
        label: Some("pipeline layout"), bind_group_layouts: &[&layout], push_constant_ranges: &[],
    });
    
    let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
        label: Some("PoW pipeline"), layout: Some(&pipeline_layout),
        module: &shader, entry_point: "main",
        compilation_options: Default::default(),
        cache: None,
    });

    // Échauffement hors chronométrage
    let warmup = Params { base_nonce: 0, difficulty: 1, count: 256, padding: 0 };
    queue.write_buffer(&params_buffer, 0, bytemuck::bytes_of(&warmup));
    queue.write_buffer(&result_buffer, 0, bytemuck::cast_slice(&[0u32, u32::MAX]));
    
    let mut encoder = device.create_command_encoder(
        &wgpu::CommandEncoderDescriptor { label: Some("warmup encoder") }
    );
    {
        let mut pass = encoder.begin_compute_pass(
            &wgpu::ComputePassDescriptor { label: Some("warmup"), timestamp_writes: None }
        );
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0, &bind_group, &[]);
        pass.dispatch_workgroups(1, 1, 1);
    }
    queue.submit(Some(encoder.finish()));
    device.poll(wgpu::Maintain::Wait);

    let start = Instant::now();
    let mut base = 0u32;
    let mut hashes = 0u64;
    
    loop {
        let remaining = MAX_NONCE - base;
        if remaining == 0 {
            return Ok((MAX_NONCE, hashes, device_name, start.elapsed().as_secs_f64()));
        }
        
        let count = GPU_BATCH.min(remaining);
        let params = Params { base_nonce: base, difficulty, count, padding: 0 };
        queue.write_buffer(&params_buffer, 0, bytemuck::bytes_of(&params));
        queue.write_buffer(&result_buffer, 0, bytemuck::cast_slice(&[0u32, u32::MAX]));
        
        let mut encoder = device.create_command_encoder(
            &wgpu::CommandEncoderDescriptor { label: Some("encoder") }
        );
        {
            let mut pass = encoder.begin_compute_pass(
                &wgpu::ComputePassDescriptor { label: Some("compute"), timestamp_writes: None }
            );
            pass.set_pipeline(&pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.dispatch_workgroups((count + 255) / 256, 1, 1);
        }
        encoder.copy_buffer_to_buffer(&result_buffer, 0, &read_buffer, 0, 8);
        queue.submit(Some(encoder.finish()));

        let slice = read_buffer.slice(..);
        let (tx, rx) = mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| { tx.send(result).ok(); });
        device.poll(wgpu::Maintain::Wait);
        rx.recv().map_err(|error| error.to_string())?.map_err(|error| error.to_string())?;
        
        let data = slice.get_mapped_range();
        let values: &[u32] = bytemuck::cast_slice(&data);
        let found = values[0] != 0;
        let nonce = values[1];
        drop(data);
        read_buffer.unmap();
        hashes += count as u64;

        if found {
            println!("Nonce trouvé: {}", nonce);
            println!("Hash calculés: {}", hashes);
            println!("Temps: {:.3} secondes", start.elapsed().as_secs_f64());
            println!("Performance: {:.2} hash/s", hashes as f64 / start.elapsed().as_secs_f64());
            return Ok((nonce, hashes, device_name, start.elapsed().as_secs_f64()));
        }
        
        base = base.checked_add(count).ok_or("Dépassement de l'espace des nonces")?;
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let difficulty: u32 = args.get(1)
        .and_then(|v| v.parse().ok())
        .unwrap_or(6);
    
    println!("=== WobblyToken PoW v2 - GPU SHA-256 ===");
    println!("Difficulté: {} ({} bits)", difficulty, difficulty * 4);
    println!("Recherche du nonce...");
    
    match pollster::block_on(run_gpu(difficulty)) {
        Ok((nonce, hashes, device, elapsed)) => {
            println!("\n=== Résultat ===");
            println!("GPU: {}", device);
            println!("Nonce: {}", nonce);
            println!("Nonce (hex): 0x{:08x}", nonce);
            println!("Hashes: {}", hashes);
            println!("Temps: {:.3} secondes", elapsed);
            println!("Performance: {:.2} hash/s", hashes as f64 / elapsed);
        }
        Err(e) => {
            eprintln!("Erreur: {}", e);
        }
    }
}