//! Task Scheduler CLI
//!
//! A command-line tool for managing scheduled jobs.
//!
//! # Usage
//!
//! ```text
//! taskctl add backup --command "backup.sh" --cron "0 2 * * *"
//! taskctl list
//! taskctl run backup
//! taskctl status
//! ```

use clap::{Parser, Subcommand, Args};
use task_scheduler::{
    Job, JobId, Scheduler, SchedulerError, Priority, Result,
    job::Schedule,
    scheduler::CronExpression,
    utils::{format_duration, format_relative_time, truncate},
};
use chrono::Utc;

/// Task Scheduler - Manage and run scheduled jobs
#[derive(Parser, Debug)]
#[command(name = "taskctl")]
#[command(author, version, about, long_about = None)]
#[command(propagate_version = true)]
struct Cli {
    /// Path to the jobs storage file
    #[arg(short, long, default_value = "jobs.json", global = true)]
    file: String,

    /// Enable verbose output
    #[arg(short, long, global = true)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Add a new job
    Add(AddArgs),

    /// Remove a job
    Remove {
        /// Job name or ID
        name: String,
    },

    /// List all jobs
    List(ListArgs),

    /// Show job details
    Show {
        /// Job name or ID
        name: String,
    },

    /// Run a job immediately
    Run {
        /// Job name or ID
        name: String,
    },

    /// Run all pending jobs
    RunPending,

    /// Enable a job
    Enable {
        /// Job name or ID
        name: String,
    },

    /// Disable a job
    Disable {
        /// Job name or ID
        name: String,
    },

    /// Show scheduler status
    Status,

    /// Validate a cron expression
    ValidateCron {
        /// Cron expression to validate
        expression: String,
    },

    /// Show next N occurrences of a schedule
    NextRuns {
        /// Cron expression or job name
        schedule: String,

        /// Number of occurrences to show
        #[arg(short, long, default_value = "5")]
        count: usize,
    },

    /// Initialize with sample jobs
    Init {
        /// Overwrite existing jobs
        #[arg(long)]
        force: bool,
    },

    /// Export jobs to JSON
    Export {
        /// Output file (stdout if not specified)
        #[arg(short, long)]
        output: Option<String>,
    },

    /// Import jobs from JSON
    Import {
        /// Input file
        file: String,

        /// Skip existing jobs instead of failing
        #[arg(long)]
        skip_existing: bool,
    },
}

#[derive(Args, Debug)]
struct AddArgs {
    /// Job name (alphanumeric, hyphens, underscores)
    name: String,

    /// Shell command to execute
    #[arg(short, long, required_unless_present = "manual")]
    command: Option<String>,

    /// Cron schedule expression
    #[arg(long, conflicts_with_all = ["interval", "once", "manual"])]
    cron: Option<String>,

    /// Run every N seconds
    #[arg(long, conflicts_with_all = ["cron", "once", "manual"])]
    interval: Option<u64>,

    /// Run once at specific time (ISO 8601)
    #[arg(long, conflicts_with_all = ["cron", "interval", "manual"])]
    once: Option<String>,

    /// Manual trigger only
    #[arg(long, conflicts_with_all = ["cron", "interval", "once"])]
    manual: bool,

    /// Job description
    #[arg(short, long)]
    description: Option<String>,

    /// Priority: low, normal, high, critical
    #[arg(short, long, default_value = "normal")]
    priority: String,

    /// Maximum retry attempts
    #[arg(long, default_value = "3")]
    retries: u8,

    /// Timeout in seconds
    #[arg(long)]
    timeout: Option<u64>,

    /// Tags (comma-separated)
    #[arg(short, long)]
    tags: Option<String>,

    /// Start job disabled
    #[arg(long)]
    disabled: bool,
}

#[derive(Args, Debug)]
struct ListArgs {
    /// Filter by state: pending, running, completed, failed
    #[arg(long)]
    state: Option<String>,

    /// Filter by tag
    #[arg(long)]
    tag: Option<String>,

    /// Filter by priority
    #[arg(long)]
    priority: Option<String>,

    /// Show only enabled jobs
    #[arg(long)]
    enabled: bool,

    /// Show only disabled jobs
    #[arg(long)]
    disabled: bool,

    /// Output format: table, json, csv
    #[arg(short, long, default_value = "table")]
    format: String,
}

fn main() {
    if let Err(e) = run() {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Add(args) => cmd_add(&cli.file, args),
        Commands::Remove { name } => cmd_remove(&cli.file, &name),
        Commands::List(args) => cmd_list(&cli.file, args),
        Commands::Show { name } => cmd_show(&cli.file, &name),
        Commands::Run { name } => cmd_run(&cli.file, &name),
        Commands::RunPending => cmd_run_pending(&cli.file),
        Commands::Enable { name } => cmd_enable(&cli.file, &name),
        Commands::Disable { name } => cmd_disable(&cli.file, &name),
        Commands::Status => cmd_status(&cli.file),
        Commands::ValidateCron { expression } => cmd_validate_cron(&expression),
        Commands::NextRuns { schedule, count } => cmd_next_runs(&cli.file, &schedule, count),
        Commands::Init { force } => cmd_init(&cli.file, force),
        Commands::Export { output } => cmd_export(&cli.file, output),
        Commands::Import { file, skip_existing } => cmd_import(&cli.file, &file, skip_existing),
    }
}

fn cmd_add(storage_path: &str, args: AddArgs) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    // Build job
    let mut builder = Job::builder()
        .name(&args.name)
        .retries(args.retries)
        .enabled(!args.disabled);

    // Set description
    if let Some(desc) = args.description {
        builder = builder.description(desc);
    }

    // Set schedule
    if let Some(cron) = args.cron {
        // Validate cron first
        CronExpression::parse(&cron)?;
        builder = builder.schedule(&cron);
    } else if let Some(secs) = args.interval {
        builder = builder.every_secs(secs);
    } else if let Some(time_str) = args.once {
        let dt = chrono::DateTime::parse_from_rfc3339(&time_str)
            .map_err(|e| SchedulerError::validation("once", format!("invalid datetime: {}", e)))?
            .with_timezone(&Utc);
        builder = builder.once_at(dt);
    } else if args.manual {
        builder = builder.manual();
    } else {
        builder = builder.manual();
    }

    // Set command
    if let Some(cmd) = args.command {
        builder = builder.command(cmd);
    }

    // Set priority
    let priority = match args.priority.to_lowercase().as_str() {
        "low" => Priority::Low,
        "normal" => Priority::Normal,
        "high" => Priority::High,
        "critical" => Priority::Critical,
        _ => return Err(SchedulerError::validation(
            "priority",
            "must be one of: low, normal, high, critical",
        )),
    };
    builder = builder.priority(priority);

    // Set timeout
    if let Some(timeout) = args.timeout {
        builder = builder.timeout(timeout);
    }

    // Set tags
    if let Some(tags_str) = args.tags {
        let tags: Vec<&str> = tags_str.split(',').map(|s| s.trim()).collect();
        builder = builder.tags(tags);
    }

    let job = builder.build()?;
    let id = scheduler.add(job)?;

    println!("Created job '{}' with ID: {}", args.name, id);
    Ok(())
}

fn cmd_remove(storage_path: &str, name: &str) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    // Try by name first, then by ID
    let removed = if scheduler.contains_name(name) {
        scheduler.remove_by_name(name)?
    } else if let Ok(id) = JobId::parse(name) {
        scheduler.remove(id)?
    } else {
        return Err(SchedulerError::validation("name", format!("job not found: {}", name)));
    };

    println!("Removed job: {}", removed.name());
    Ok(())
}

fn cmd_list(storage_path: &str, args: ListArgs) -> Result<()> {
    let scheduler = Scheduler::new(storage_path)?;

    if scheduler.is_empty() {
        println!("No jobs found.");
        return Ok(());
    }

    // Filter jobs
    let jobs: Vec<_> = scheduler.jobs()
        .filter(|job| {
            if let Some(ref state) = args.state {
                if job.state().name() != state {
                    return false;
                }
            }
            if let Some(ref tag) = args.tag {
                if !job.tags().contains(tag) {
                    return false;
                }
            }
            if args.enabled && !job.is_enabled() {
                return false;
            }
            if args.disabled && job.is_enabled() {
                return false;
            }
            true
        })
        .collect();

    if jobs.is_empty() {
        println!("No jobs match the filter.");
        return Ok(());
    }

    match args.format.as_str() {
        "json" => {
            let json = serde_json::to_string_pretty(&jobs)?;
            println!("{}", json);
        }
        "csv" => {
            println!("name,state,enabled,priority,schedule");
            for job in &jobs {
                let schedule = match job.schedule() {
                    Schedule::Cron { expression } => expression.clone(),
                    Schedule::Interval { seconds } => format!("every {}s", seconds),
                    Schedule::Once { at } => format!("once at {}", at),
                    Schedule::Manual => "manual".to_string(),
                };
                println!("{},{},{},{},{}",
                    job.name(),
                    job.state().name(),
                    job.is_enabled(),
                    job.priority(),
                    schedule
                );
            }
        }
        _ => {
            // Table format
            println!("{:<20} {:<12} {:<8} {:<10} {:<20}",
                "NAME", "STATE", "ENABLED", "PRIORITY", "SCHEDULE");
            println!("{}", "-".repeat(72));

            for job in &jobs {
                let schedule = match job.schedule() {
                    Schedule::Cron { expression } => truncate(expression, 18),
                    Schedule::Interval { seconds } => format!("every {}s", seconds),
                    Schedule::Once { at } => format_relative_time(*at),
                    Schedule::Manual => "manual".to_string(),
                };

                println!("{:<20} {:<12} {:<8} {:<10} {:<20}",
                    truncate(job.name(), 18),
                    job.state().name(),
                    if job.is_enabled() { "yes" } else { "no" },
                    job.priority(),
                    schedule
                );
            }

            println!("\nTotal: {} jobs", jobs.len());
        }
    }

    Ok(())
}

fn cmd_show(storage_path: &str, name: &str) -> Result<()> {
    let scheduler = Scheduler::new(storage_path)?;

    let job = scheduler.get_by_name(name)
        .or_else(|| JobId::parse(name).ok().and_then(|id| scheduler.get(id)))
        .ok_or_else(|| SchedulerError::validation("name", format!("job not found: {}", name)))?;

    println!("Job: {}", job.name());
    println!("  ID:          {}", job.id());
    println!("  State:       {}", job.state());
    println!("  Enabled:     {}", job.is_enabled());
    println!("  Priority:    {}", job.priority());

    match job.schedule() {
        Schedule::Cron { expression } => println!("  Schedule:    cron: {}", expression),
        Schedule::Interval { seconds } => println!("  Schedule:    every {} seconds", seconds),
        Schedule::Once { at } => println!("  Schedule:    once at {}", at),
        Schedule::Manual => println!("  Schedule:    manual"),
    }

    if let Some(desc) = job.description() {
        println!("  Description: {}", desc);
    }

    println!("  Max Retries: {}", job.max_retries());

    if let Some(timeout) = job.timeout_secs() {
        println!("  Timeout:     {}s", timeout);
    }

    if !job.tags().is_empty() {
        println!("  Tags:        {}", job.tags().as_slice().join(", "));
    }

    println!("  Created:     {}", format_relative_time(job.created_at()));

    if let Some(last_run) = job.last_run() {
        println!("  Last Run:    {}", format_relative_time(last_run));
    }

    // Show history
    let history = job.history();
    if !history.is_empty() {
        println!("\n  Recent Executions:");
        for (i, record) in history.iter().rev().take(5).enumerate() {
            let status = match &record.final_state {
                task_scheduler::JobState::Completed { duration_ms, .. } => {
                    format!("completed in {}ms", duration_ms)
                }
                task_scheduler::JobState::Failed { error, .. } => {
                    format!("failed: {}", truncate(error, 30))
                }
                _ => record.final_state.name().to_string(),
            };
            println!("    {}. {} - {}", i + 1, format_relative_time(record.started_at), status);
        }
    }

    Ok(())
}

fn cmd_run(storage_path: &str, name: &str) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    if scheduler.contains_name(name) {
        scheduler.run_by_name(name)?;
    } else if let Ok(id) = JobId::parse(name) {
        scheduler.run(id)?;
    } else {
        return Err(SchedulerError::validation("name", format!("job not found: {}", name)));
    }

    println!("Job '{}' executed successfully", name);
    Ok(())
}

fn cmd_run_pending(storage_path: &str) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;
    let executed = scheduler.run_pending()?;

    if executed.is_empty() {
        println!("No pending jobs to run.");
    } else {
        println!("Executed {} jobs:", executed.len());
        for id in executed {
            if let Some(job) = scheduler.get(id) {
                println!("  - {}", job.name());
            }
        }
    }

    Ok(())
}

fn cmd_enable(storage_path: &str, name: &str) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    let id = scheduler.get_by_name(name)
        .map(|j| j.id())
        .or_else(|| JobId::parse(name).ok())
        .ok_or_else(|| SchedulerError::validation("name", format!("job not found: {}", name)))?;

    scheduler.enable(id)?;
    println!("Enabled job: {}", name);
    Ok(())
}

fn cmd_disable(storage_path: &str, name: &str) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    let id = scheduler.get_by_name(name)
        .map(|j| j.id())
        .or_else(|| JobId::parse(name).ok())
        .ok_or_else(|| SchedulerError::validation("name", format!("job not found: {}", name)))?;

    scheduler.disable(id)?;
    println!("Disabled job: {}", name);
    Ok(())
}

fn cmd_status(storage_path: &str) -> Result<()> {
    let scheduler = Scheduler::new(storage_path)?;
    let status = scheduler.status();

    println!("{}", status);
    Ok(())
}

fn cmd_validate_cron(expression: &str) -> Result<()> {
    match CronExpression::parse(expression) {
        Ok(cron) => {
            println!("Valid cron expression: {}", cron);
            println!("Description: {}", cron.describe());

            // Show next 3 occurrences
            println!("\nNext occurrences:");
            let now = Utc::now();
            let mut current = now;
            for i in 1..=3 {
                if let Some(next) = cron.next_occurrence(current) {
                    println!("  {}. {}", i, next.format("%Y-%m-%d %H:%M:%S UTC"));
                    current = next;
                }
            }

            Ok(())
        }
        Err(e) => {
            eprintln!("Invalid cron expression: {}", e);
            Err(e)
        }
    }
}

fn cmd_next_runs(storage_path: &str, schedule: &str, count: usize) -> Result<()> {
    // Try to parse as cron expression first
    let cron = if let Ok(cron) = CronExpression::parse(schedule) {
        cron
    } else {
        // Try to get schedule from job
        let scheduler = Scheduler::new(storage_path)?;
        let job = scheduler.get_by_name(schedule)
            .ok_or_else(|| SchedulerError::validation("schedule", "not a valid cron or job name"))?;

        match job.schedule() {
            Schedule::Cron { expression } => CronExpression::parse(expression)?,
            _ => return Err(SchedulerError::validation("schedule", "job does not have cron schedule")),
        }
    };

    println!("Next {} occurrences of '{}':", count, schedule);
    let now = Utc::now();
    let mut current = now;

    for i in 1..=count {
        if let Some(next) = cron.next_occurrence(current) {
            let diff = next.signed_duration_since(now);
            println!("  {}. {} ({})", i,
                next.format("%Y-%m-%d %H:%M:%S UTC"),
                format_duration(diff)
            );
            current = next;
        } else {
            break;
        }
    }

    Ok(())
}

fn cmd_init(storage_path: &str, force: bool) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    if !scheduler.is_empty() && !force {
        return Err(SchedulerError::validation(
            "init",
            "jobs already exist. Use --force to overwrite",
        ));
    }

    // Clear existing jobs if force
    if force {
        for id in scheduler.job_ids().collect::<Vec<_>>() {
            scheduler.remove(id)?;
        }
    }

    // Add sample jobs
    let samples = vec![
        Job::builder()
            .name("daily-backup")
            .description("Daily database backup")
            .schedule("0 2 * * *")
            .command("echo 'Running backup...'")
            .priority(Priority::High)
            .tags(["backup", "database"])
            .build()?,
        Job::builder()
            .name("hourly-cleanup")
            .description("Clean temporary files")
            .schedule("0 * * * *")
            .command("echo 'Cleaning up...'")
            .tags(["cleanup", "maintenance"])
            .build()?,
        Job::builder()
            .name("health-check")
            .description("System health check every 5 minutes")
            .schedule("*/5 * * * *")
            .command("echo 'Health OK'")
            .priority(Priority::Critical)
            .tags(["monitoring"])
            .build()?,
        Job::builder()
            .name("weekly-report")
            .description("Generate weekly report")
            .schedule("0 9 * * 1")
            .command("echo 'Generating report...'")
            .tags(["reports"])
            .build()?,
    ];

    for job in samples {
        scheduler.add(job)?;
    }

    println!("Initialized with {} sample jobs", scheduler.len());
    Ok(())
}

fn cmd_export(storage_path: &str, output: Option<String>) -> Result<()> {
    let scheduler = Scheduler::new(storage_path)?;
    let jobs: Vec<_> = scheduler.jobs().collect();
    let json = serde_json::to_string_pretty(&jobs)?;

    if let Some(path) = output {
        std::fs::write(&path, &json)?;
        println!("Exported {} jobs to {}", jobs.len(), path);
    } else {
        println!("{}", json);
    }

    Ok(())
}

fn cmd_import(storage_path: &str, input_file: &str, skip_existing: bool) -> Result<()> {
    let mut scheduler = Scheduler::new(storage_path)?;

    let content = std::fs::read_to_string(input_file)?;
    let jobs: Vec<Job> = serde_json::from_str(&content)?;

    let mut added = 0;
    let mut skipped = 0;

    for job in jobs {
        if scheduler.contains_name(job.name()) {
            if skip_existing {
                skipped += 1;
                continue;
            } else {
                return Err(SchedulerError::DuplicateJob(job.name().to_string()));
            }
        }

        scheduler.add(job)?;
        added += 1;
    }

    println!("Imported {} jobs ({} skipped)", added, skipped);
    Ok(())
}
