use recalltree::*;
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    let path = args.get(2).map(String::as_str).unwrap_or("demo-store");
    let engine = Engine::open(path, Limits::default())?;
    match args.get(1).map(String::as_str).unwrap_or("demo") {
        "demo" => {
            if !engine.state().runs.contains("demo-1") {
                engine.ingest(
                    "demo-1",
                    Record {
                        id: "build-observation".into(),
                        role: "builder".into(),
                        scope: "demo".into(),
                        text: "The sample build completed in the fixture.".into(),
                        kind: Kind::Observation,
                        evidence: vec![Evidence {
                            uri: "fixture://build-log".into(),
                            available: false,
                        }],
                        version: 1,
                        status: "active".into(),
                        applicability: "Synthetic demo only".into(),
                        shared: false,
                        supersedes: vec![],
                        conflicts: vec![],
                        expires_at: None,
                    },
                    b"engine-owned verbose scratch",
                )?;
                engine.finalize("demo-1", Fault::None)?;
            }
            println!(
                "{}",
                serde_json::to_string_pretty(&retrieve(
                    &engine.state(),
                    "builder",
                    "demo",
                    "build",
                    0,
                    2048
                )?)
                .unwrap()
            );
        }
        "graph" => println!("{}", serde_json::to_string_pretty(&engine.state()).unwrap()),
        _ => return Err("usage: recalltree [demo|graph] [store-directory]".into()),
    }
    Ok(())
}
