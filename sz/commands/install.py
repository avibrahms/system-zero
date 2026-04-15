from pathlib import Path
import tempfile

import click

from sz.commands import catalog
from sz.core import module_install, paths


@click.command(help="Install a module into the current repo.")
@click.argument("module_id", required=False)
@click.option("--source", type=click.Path(file_okay=False, path_type=Path), required=False, help="Local module source directory.")
@click.option("--force", is_flag=True, help="Replace an existing module with the same id.")
def cmd(module_id: str | None, source: Path | None, force: bool) -> None:
    root = paths.repo_root()
    try:
        if source is None:
            if module_id is None:
                raise module_install.ModuleInstallError("Pass a module id or --source.")
            with tempfile.TemporaryDirectory(prefix=f"sz-catalog-{module_id}-") as tmp:
                fetched = catalog.fetch_module(module_id, Path(tmp))
                resolved_module_id = module_install.install_from_source(root, fetched, module_id, force=force)
                click.echo(f"Installed {resolved_module_id} from catalog")
                return
        resolved_module_id = module_install.install_from_source(root, source, module_id, force=force)
    except module_install.ModuleInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    except catalog.CatalogError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Installed {resolved_module_id} from {source}")
