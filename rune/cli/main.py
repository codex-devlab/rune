import typer
from rune.cli.analyze import analyze_cmd
from rune.cli.init_cmd import init_cmd
from rune.cli.patch import patch_app
from rune.cli.scaffold import scaffold_cmd
from rune.cli.watch import watch_cmd

app = typer.Typer(name="rune", help="Static Instruction Injection Optimizer")
app.command("analyze")(analyze_cmd)
app.command("init")(init_cmd)
app.command("scaffold")(scaffold_cmd)
app.command("watch")(watch_cmd)
app.add_typer(patch_app, name="patch")
