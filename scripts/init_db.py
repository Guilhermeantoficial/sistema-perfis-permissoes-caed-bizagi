"""Compatibilidade: aplica migrações e cria dados iniciais.

Prefira `python -m app.cli migrate` e `python -m app.cli seed` em automações.
"""
from app.cli import command_migrate, command_seed


if __name__ == "__main__":
    command_migrate()
    command_seed()
