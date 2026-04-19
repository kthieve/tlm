# Project form

Edit the values under each `##` heading. Do not rename headings.

## Project Name

tlm

## Language / Framework

Python

## Project Type

CLI

## Description

Its a cli program for linux terminal using python built in gui for configuration. it does the following
     - User can directly ask question using "tlm ? How to find out the Ubuntu version and kernel of my pc"
     - The program will call llm using providers (openai, deepseek, chutes, openrouter, nano-gpt)
     - the llm will send answer
     - it has sessions and context
     - Gui provides chat history, api key configuration, permissions, ask and other featuers and logs, token usage etc (with graphs and requests)
     - it can write scripts to new files and do stuff (BUT ONLY WITH EXPLICIT PERMISSION)
     - for code write mode i say tlm write me a program to clean my apt and python cache and recover drive space
     - for code execution i say tlm do what is my cpu temperature
     - for both code writing and execution it MUST show me what its going to execute and ask for permission.



## Target Platform

Linux

## Dependencies / Tools

<!-- list packages, CLIs, or runtimes -->

## Note
 - Add a list of other necessary and security important features (like preventing harmful commands)

## Core Features

- Ask the model from the terminal (`tlm ? …` / `tlm ask …`) with session JSON and multi-provider support.
- Tk GUI for keys, chat history, permissions, token usage, and logs (phased).
- Write mode and do mode always show a preview and require explicit confirmation.
- Denylist and safe argv parsing for `do` (expand over time).

## Scale

Small

## Documentation Level

Standard

## Additional Notes

- Security backlog: deny dangerous shell patterns, optional allowlist profile, redact secrets in logs, subprocess timeouts, no `shell=True` for untrusted input, atomic file writes in write mode.
