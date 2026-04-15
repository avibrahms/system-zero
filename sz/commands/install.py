from pathlib import Path

import click

from sz.core import module_install, paths


@click.command(help="Install a module into the current repo.")
@click.argument("module_id", required=False)
@click.option("--source", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True, help="Local module source directory.")
@click.option("--force", is_flag=True, help="Replace an existing module with the same id.")
def cmd(module_id: str | None, source: Path, force: bool) -> None:
    root = paths.repo_root()
    try:
        resolved_module_id = module_install.install_from_source(root, source, module_id, force=force)
    except module_install.ModuleInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Installed {resolved_module_id} from {source}")
