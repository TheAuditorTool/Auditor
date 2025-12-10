"""GraphQL schema analysis and resolver mapping."""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.logging import logger


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def graphql():
    """GraphQL schema analysis and resolver-to-field mapping for security and taint analysis.

    Group command for analyzing GraphQL schemas, correlating resolvers with fields, and
    building execution graphs for data flow analysis. Enables GraphQL-specific security
    rules and taint tracking through the GraphQL execution layer.

    AI ASSISTANT CONTEXT:
      Purpose: Map GraphQL schema to backend resolvers for security analysis
      Input: .pf/repo_index.db (code index with graphql_* tables)
      Output: Resolver mappings, execution edges, findings cache
      Prerequisites: aud full (extracts SDL schemas + resolver patterns)
      Integration: Taint analysis, security rules, data flow tracking
      Performance: ~2-10 seconds (schema correlation + graph construction)

    SUBCOMMANDS:
      build:   Correlate SDL schemas with resolver implementations
      query:   Query GraphQL metadata (types, fields, resolvers)
      viz:     Visualize GraphQL execution graph

    GRAPHQL ANALYSIS PIPELINE:
      1. SDL Extraction: Parse .graphql/.gql files (schema types/fields)
      2. Resolver Detection: Find @Resolver decorators, resolve_* methods
      3. Correlation: Match fields → resolver functions via symbol table
      4. Execution Graph: Build field → resolver → downstream call edges
      5. Taint Integration: Seed taint frontier with GraphQL arguments

    INSIGHTS PROVIDED:
      - Resolver coverage (which fields have implementations)
      - Missing resolvers (schema fields without implementations)
      - Execution paths (field → resolver → database/API calls)
      - Argument mapping (GraphQL args → function parameters)

    TYPICAL WORKFLOW:
      aud full                     # Extract SDL + resolvers
      aud graphql build            # Correlate and build execution graph
      aud graphql query --type User  # Inspect User type fields
      aud taint                    # Use GraphQL edges for taint

    EXAMPLES:
      aud graphql build
      aud graphql query --type Query --show-resolvers
      aud graphql viz --output schema.svg

    PERFORMANCE:
      Small (<10 types):    ~1-2 seconds
      Medium (50 types):    ~3-5 seconds
      Large (200+ types):   ~5-10 seconds

    RELATED COMMANDS:
      aud full         # Extracts GraphQL schemas and resolvers
      aud taint        # Uses GraphQL execution edges
      aud graph        # Generic call graph (GraphQL adds field layer)

    NOTE: GraphQL data stored in repo_index.db (graphql_* tables).
    The build command adds resolver_mappings and execution_edges.

    EXAMPLE:
      aud graphql query --field user --show-resolvers

    SEE ALSO:
      aud manual graphql   Learn about GraphQL schema and resolver analysis
    """
    pass


@graphql.command("build", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--db", default="./.pf/repo_index.db", help="Repository index database")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def graphql_build(root, db, verbose):
    """Build GraphQL resolver mappings and execution graph.

    Correlates GraphQL SDL schemas with resolver implementations:
    1. Load graphql_types and graphql_fields from SDL extraction
    2. Load symbols table (all function definitions)
    3. Match resolvers to fields via naming conventions + decorators
    4. Create graphql_resolver_mappings entries
    5. Build execution graph edges (field → resolver → downstream)

    Examples:
      aud graphql build                    # Default database
      aud graphql build --verbose          # Show correlation details
      aud graphql build --db custom.db     # Custom database path

    Correlation Strategies:
      - Graphene: resolve_<field> methods in ObjectType classes
      - Ariadne: @query.field("name") decorator → function mapping
      - Strawberry: @strawberry.field on class methods
      - Apollo: resolvers object mapping (Query.field → function)
      - NestJS: @Query()/@Mutation() decorators with field names
      - TypeGraphQL: @Resolver()/@Query() with return type inference

    Output:
      Updates graphql_resolver_mappings table
      Updates graphql_resolver_params table
      Updates graphql_execution_edges table
      Creates execution graph for taint analysis
    """
    from theauditor.graph.graphql.builder import GraphQLBuilder

    db_path = Path(root) / db
    if not db_path.exists():
        err_console.print(f"[error]Error: Database not found at {db_path}[/error]", highlight=False)
        err_console.print(
            "[error]Run 'aud full' first to extract GraphQL schemas[/error]",
        )
        return 1

    logger.info(f"Building GraphQL resolver mappings from {db_path}")

    builder = GraphQLBuilder(db_path, verbose=verbose)

    try:
        console.print("Phase 1: Loading GraphQL schemas...")
        schemas_count = builder.load_schemas()
        console.print(f"  Loaded {schemas_count} schema files", highlight=False)

        console.print("Phase 2: Loading resolver candidates...")
        resolvers_count = builder.load_resolver_candidates()
        console.print(f"  Found {resolvers_count} potential resolvers", highlight=False)

        console.print("Phase 3: Correlating fields with resolvers...")
        mappings_count = builder.correlate_resolvers()
        console.print(f"  Created {mappings_count} resolver mappings", highlight=False)

        console.print("Phase 4: Building execution graph...")
        edges_count = builder.build_execution_graph()
        console.print(f"  Created {edges_count} execution edges", highlight=False)

        console.print("\nGraphQL build complete!")
        console.print(
            f"  Resolver coverage: {builder.get_coverage_percent():.1f}%", highlight=False
        )
        console.print(f"  Missing resolvers: {builder.get_missing_count()}", highlight=False)

        if verbose:
            builder.print_summary()

        return 0

    except Exception as e:
        logger.error(f"GraphQL build failed: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        return 1


@graphql.command("query", cls=RichCommand)
@click.option("--db", default="./.pf/repo_index.db", help="Repository index database")
@click.option("--type", "type_name", help="Query specific GraphQL type")
@click.option("--field", "field_name", help="Query specific field")
@click.option("--show-resolvers", is_flag=True, help="Show resolver mappings")
@click.option("--show-args", is_flag=True, help="Show field arguments")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graphql_query(db, type_name, field_name, show_resolvers, show_args, output_json):
    """Query GraphQL schema metadata and resolver mappings.

    Examples:
      aud graphql query --type Query
      aud graphql query --field user --show-resolvers
      aud graphql query --type Mutation --show-args
      aud graphql query --json > schema.json
    """
    from theauditor.graph.graphql.querier import GraphQLQuerier

    db_path = Path(db)
    if not db_path.exists():
        err_console.print(f"[error]Error: Database not found at {db_path}[/error]", highlight=False)
        return 1

    querier = GraphQLQuerier(db_path)

    try:
        if type_name:
            result = querier.query_type(
                type_name, show_resolvers=show_resolvers, show_args=show_args
            )
        elif field_name:
            result = querier.query_field(field_name, show_resolvers=show_resolvers)
        else:
            result = querier.query_all_types()

        if output_json:
            console.print(json.dumps(result, indent=2), markup=False)
        else:
            querier.print_result(result)

        return 0

    except Exception as e:
        logger.error(f"GraphQL query failed: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        return 1


@graphql.command("viz", cls=RichCommand)
@click.option("--db", default="./.pf/repo_index.db", help="Repository index database")
@click.option("--output", "-o", default="graphql_schema.svg", help="Output file path")
@click.option("--format", default="svg", help="Output format (svg, png, dot)")
@click.option("--type", "type_filter", help="Filter to specific type")
def graphql_viz(db, output, format, type_filter):
    """Visualize GraphQL schema and execution graph.

    Examples:
      aud graphql viz                           # Generate SVG
      aud graphql viz --format png -o schema.png
      aud graphql viz --type Query              # Only Query type
    """
    from theauditor.graph.graphql.visualizer import GraphQLVisualizer

    db_path = Path(db)
    if not db_path.exists():
        err_console.print(f"[error]Error: Database not found at {db_path}[/error]", highlight=False)
        return 1

    visualizer = GraphQLVisualizer(db_path)

    try:
        console.print("Generating GraphQL visualization...")
        visualizer.generate(output_path=output, output_format=format, type_filter=type_filter)
        console.print(f"Visualization saved to {output}", highlight=False)
        return 0

    except Exception as e:
        logger.error(f"GraphQL visualization failed: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        return 1
