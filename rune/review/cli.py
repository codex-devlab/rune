import typer

review_app = typer.Typer(help="Review rules for conflicts and dead rules")


@review_app.callback(invoke_without_command=True)
def main(json: bool = typer.Option(False, "--json")):
    if json:
        print('{"schema_version": "1.0", "conflicts": [], "dead_candidates": []}')
    else:
        print("review v0.2 scaffold")
