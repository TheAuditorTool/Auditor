//! Calorie Tracker CLI - Track your daily food intake and nutrition goals.
//!
//! Usage:
//!   caltrack add "Chicken Breast" --calories 165 --protein 31
//!   caltrack log breakfast "2 eggs, toast"
//!   caltrack summary --date today
//!   caltrack goal set --calories 2000 --protein 150
//!   caltrack serve --port 8080  # Start API server

use clap::{Parser, Subcommand};
use tracing::{info, error, Level};
use tracing_subscriber::FmtSubscriber;

use calorie_tracker::{
    models::{Food, Meal, MealType, User, DailyGoal},
    storage::{Repository, SqliteRepository},
    api,
    CalorieTrackerError, Result,
};

/// Calorie Tracker - Your personal nutrition assistant
#[derive(Parser, Debug)]
#[command(name = "caltrack")]
#[command(author, version, about, long_about = None)]
struct Cli {
    /// Enable verbose logging
    #[arg(short, long, global = true)]
    verbose: bool,

    /// Database file path
    #[arg(short, long, default_value = "calories.db")]
    database: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Add a food item to the database
    Add {
        /// Name of the food
        name: String,
        /// Calories per serving
        #[arg(short, long)]
        calories: u32,
        /// Protein in grams
        #[arg(short, long, default_value = "0")]
        protein: f32,
        /// Carbs in grams
        #[arg(short = 'b', long, default_value = "0")]
        carbs: f32,
        /// Fat in grams
        #[arg(short, long, default_value = "0")]
        fat: f32,
        /// Serving size description
        #[arg(short, long, default_value = "1 serving")]
        serving: String,
    },

    /// Log a meal
    Log {
        /// Meal type: breakfast, lunch, dinner, snack
        meal_type: String,
        /// Description of what you ate
        description: String,
        /// Food IDs to associate (comma-separated)
        #[arg(short, long)]
        foods: Option<String>,
    },

    /// Show daily summary
    Summary {
        /// Date to summarize (YYYY-MM-DD or 'today')
        #[arg(short, long, default_value = "today")]
        date: String,
    },

    /// Manage daily goals
    Goal {
        #[command(subcommand)]
        action: GoalAction,
    },

    /// List foods in database
    Foods {
        /// Search term
        #[arg(short, long)]
        search: Option<String>,
        /// Maximum results
        #[arg(short, long, default_value = "20")]
        limit: usize,
    },

    /// Start the HTTP API server
    #[cfg(feature = "api")]
    Serve {
        /// Port to listen on
        #[arg(short, long, default_value = "8080")]
        port: u16,
        /// Host to bind to
        #[arg(long, default_value = "127.0.0.1")]
        host: String,
    },

    /// Initialize database with sample data
    Init {
        /// Include sample foods
        #[arg(long)]
        with_samples: bool,
    },
}

#[derive(Subcommand, Debug)]
enum GoalAction {
    /// Set daily goals
    Set {
        #[arg(short, long)]
        calories: Option<u32>,
        #[arg(short, long)]
        protein: Option<f32>,
        #[arg(short = 'b', long)]
        carbs: Option<f32>,
        #[arg(short, long)]
        fat: Option<f32>,
    },
    /// Show current goals
    Show,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Setup logging
    let level = if cli.verbose { Level::DEBUG } else { Level::INFO };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .finish();
    tracing::subscriber::set_global_default(subscriber)
        .expect("Failed to set tracing subscriber");

    info!("Calorie Tracker starting...");

    // Initialize repository
    let repo = SqliteRepository::new(&cli.database).await?;

    match cli.command {
        Commands::Add { name, calories, protein, carbs, fat, serving } => {
            let food = Food::new(name, calories, protein, carbs, fat, serving);
            let id = repo.save_food(&food).await?;
            println!("Added food with ID: {}", id);
        }

        Commands::Log { meal_type, description, foods } => {
            let meal_type = parse_meal_type(&meal_type)?;
            let food_ids: Vec<uuid::Uuid> = foods
                .map(|f| parse_food_ids(&f))
                .transpose()?
                .unwrap_or_default();

            let meal = Meal::new(meal_type, description, food_ids);
            let id = repo.save_meal(&meal).await?;
            println!("Logged meal with ID: {}", id);
        }

        Commands::Summary { date } => {
            let date = parse_date(&date)?;
            let summary = repo.get_daily_summary(date).await?;
            print_summary(&summary);
        }

        Commands::Goal { action } => match action {
            GoalAction::Set { calories, protein, carbs, fat } => {
                let mut goal = repo.get_current_goal().await?.unwrap_or_default();
                if let Some(c) = calories { goal.calories = c; }
                if let Some(p) = protein { goal.protein = p; }
                if let Some(c) = carbs { goal.carbs = c; }
                if let Some(f) = fat { goal.fat = f; }
                repo.save_goal(&goal).await?;
                println!("Goals updated successfully");
            }
            GoalAction::Show => {
                if let Some(goal) = repo.get_current_goal().await? {
                    println!("Daily Goals:");
                    println!("  Calories: {} kcal", goal.calories);
                    println!("  Protein:  {:.1} g", goal.protein);
                    println!("  Carbs:    {:.1} g", goal.carbs);
                    println!("  Fat:      {:.1} g", goal.fat);
                } else {
                    println!("No goals set. Use 'caltrack goal set' to configure.");
                }
            }
        },

        Commands::Foods { search, limit } => {
            let foods = repo.search_foods(search.as_deref(), limit).await?;
            if foods.is_empty() {
                println!("No foods found.");
            } else {
                println!("{:<36} {:<30} {:>8} {:>8}", "ID", "Name", "Calories", "Protein");
                println!("{}", "-".repeat(86));
                for food in foods {
                    println!(
                        "{:<36} {:<30} {:>8} {:>7.1}g",
                        food.id, food.name, food.calories, food.protein
                    );
                }
            }
        }

        #[cfg(feature = "api")]
        Commands::Serve { port, host } => {
            info!("Starting API server on {}:{}", host, port);
            api::serve(&host, port, repo).await?;
        }

        Commands::Init { with_samples } => {
            repo.initialize().await?;
            if with_samples {
                initialize_sample_data(&repo).await?;
            }
            println!("Database initialized successfully");
        }
    }

    Ok(())
}

fn parse_meal_type(s: &str) -> Result<MealType> {
    match s.to_lowercase().as_str() {
        "breakfast" => Ok(MealType::Breakfast),
        "lunch" => Ok(MealType::Lunch),
        "dinner" => Ok(MealType::Dinner),
        "snack" => Ok(MealType::Snack),
        _ => Err(CalorieTrackerError::InvalidInput(
            format!("Unknown meal type: {}. Use breakfast, lunch, dinner, or snack.", s)
        )),
    }
}

fn parse_food_ids(s: &str) -> Result<Vec<uuid::Uuid>> {
    s.split(',')
        .map(|id| {
            uuid::Uuid::parse_str(id.trim())
                .map_err(|_| CalorieTrackerError::InvalidInput(format!("Invalid food ID: {}", id)))
        })
        .collect()
}

fn parse_date(s: &str) -> Result<chrono::NaiveDate> {
    if s == "today" {
        Ok(chrono::Local::now().date_naive())
    } else {
        chrono::NaiveDate::parse_from_str(s, "%Y-%m-%d")
            .map_err(|_| CalorieTrackerError::InvalidInput(
                format!("Invalid date: {}. Use YYYY-MM-DD or 'today'.", s)
            ))
    }
}

fn print_summary(summary: &calorie_tracker::models::DailySummary) {
    println!("\n=== Daily Summary for {} ===\n", summary.date);

    if summary.meals.is_empty() {
        println!("No meals logged for this date.");
        return;
    }

    for meal in &summary.meals {
        println!("{}: {}", meal.meal_type, meal.description);
    }

    println!("\n--- Totals ---");
    println!("Calories: {} kcal", summary.total_calories);
    println!("Protein:  {:.1} g", summary.total_protein);
    println!("Carbs:    {:.1} g", summary.total_carbs);
    println!("Fat:      {:.1} g", summary.total_fat);

    if let Some(ref goal) = summary.goal {
        println!("\n--- vs Goals ---");
        let cal_pct = (summary.total_calories as f32 / goal.calories as f32) * 100.0;
        println!("Calories: {:.0}% of {} kcal goal", cal_pct, goal.calories);
    }
}

async fn initialize_sample_data(repo: &SqliteRepository) -> Result<()> {
    let sample_foods = vec![
        Food::new("Chicken Breast (grilled)", 165, 31.0, 0.0, 3.6, "100g"),
        Food::new("Brown Rice", 216, 5.0, 45.0, 1.8, "1 cup cooked"),
        Food::new("Broccoli (steamed)", 55, 3.7, 11.0, 0.6, "1 cup"),
        Food::new("Egg (large)", 72, 6.3, 0.4, 4.8, "1 egg"),
        Food::new("Salmon (baked)", 208, 20.0, 0.0, 13.0, "100g"),
        Food::new("Greek Yogurt", 100, 17.0, 6.0, 0.7, "170g container"),
        Food::new("Banana", 105, 1.3, 27.0, 0.4, "1 medium"),
        Food::new("Oatmeal", 150, 5.0, 27.0, 2.5, "1 cup cooked"),
        Food::new("Almonds", 164, 6.0, 6.0, 14.0, "1 oz (23 nuts)"),
        Food::new("Sweet Potato", 103, 2.3, 24.0, 0.1, "1 medium"),
    ];

    for food in sample_foods {
        repo.save_food(&food).await?;
    }

    info!("Added {} sample foods", 10);
    Ok(())
}
