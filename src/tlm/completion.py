"""Shell completion scripts for bash/zsh/fish."""

from __future__ import annotations


def emit(shell: str) -> str:
    s = shell.lower().strip()
    if s == "bash":
        return _BASH
    if s == "zsh":
        return _ZSH
    if s == "fish":
        return _FISH
    raise ValueError(f"unsupported shell: {shell!r}")


_BASH = r"""
_tlm() {
  local cur
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  if [ "${COMP_CWORD}" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "gui ask write do providers sessions usage completion init config new harvest help paths allow unallow update ?" -- "${cur}") )
  elif [ "${COMP_CWORD}" -eq 2 ] && [ "${COMP_WORDS[1]}" = "init" ]; then
    COMPREPLY=( $(compgen -W "--wizard --no-wizard" -- "${cur}") )
  fi
}
complete -F _tlm tlm
""".strip()


_ZSH = r"""
#compdef tlm
_tlm() {
  local -a cmds
  cmds=(gui ask write do providers sessions usage completion new harvest help paths allow unallow update '?:help')
  _arguments '1: :->cmd' '*:: :->args'
  case $state in
    cmd) _describe -t commands command cmds ;;
    args) _files ;;
  esac
}
compdef _tlm tlm
""".strip()


_FISH = r"""
complete -c tlm -n "__fish_use_subcommand" -a init -d "Create dirs and default config"
complete -c tlm -n '__fish_seen_subcommand_from init' -l wizard -d "Run setup wizard after init"
complete -c tlm -n '__fish_seen_subcommand_from init' -l no-wizard -d "Skip setup wizard prompts"
complete -c tlm -n "__fish_use_subcommand" -a config -d "TUI settings (config gui for window)"
complete -c tlm -n "__fish_use_subcommand" -a gui -d "Tk configuration UI"
complete -c tlm -n "__fish_use_subcommand" -a ask -d "Ask the model"
complete -c tlm -n "__fish_use_subcommand" -a write -d "Write files (confirm)"
complete -c tlm -n "__fish_use_subcommand" -a do -d "Run commands (confirm)"
complete -c tlm -n "__fish_use_subcommand" -a providers -d "List providers"
complete -c tlm -n "__fish_use_subcommand" -a sessions -d "Session TUI or list/resume/…"
complete -c tlm -n "__fish_use_subcommand" -a new -d "New named session"
complete -c tlm -n "__fish_use_subcommand" -a harvest -d "Harvest facts to memory"
complete -c tlm -n "__fish_use_subcommand" -a usage -d "Token/cost usage"
complete -c tlm -n "__fish_use_subcommand" -a completion -d "Print shell completion"
complete -c tlm -n "__fish_use_subcommand" -a paths -d "Show permissions freelist"
complete -c tlm -n "__fish_use_subcommand" -a allow -d "Add freelist path"
complete -c tlm -n "__fish_use_subcommand" -a unallow -d "Remove freelist path"
complete -c tlm -n "__fish_use_subcommand" -a update -d "Upgrade from GitHub"
""".strip()
