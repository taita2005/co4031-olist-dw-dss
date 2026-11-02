# Shared settings, sourced by the other scripts (or by you: `source scripts/env.sh`,
# works in bash and zsh). Everything lives inside the project folder.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")/.." && pwd)"
export MAMBA_ROOT_PREFIX="$PROJECT_ROOT/.mamba"
MICROMAMBA="$PROJECT_ROOT/.tools/micromamba"
ENV_PREFIX="$PROJECT_ROOT/.env-btl"
PGDATA_DIR="$PROJECT_ROOT/.pgdata"

export PGHOST=localhost
export PGPORT=5433            # avoid clashing with any system PostgreSQL on 5432
export PGUSER=btl
export PGDATABASE=olist_dw
export PATH="$ENV_PREFIX/bin:$PATH"
