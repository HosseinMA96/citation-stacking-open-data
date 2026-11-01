#!/usr/bin/env bash
# Run ON THE VM once, after vm/vmctl.sh push:  bash ~/c/vm/setup_vm.sh
# Installs tmux/pigz, micromamba 2.9.0 (checksum-verified), the c-gt env, then runs the self-tests.
set -euo pipefail
C=~/c
MM_VER=2.9.0-0
sudo apt-get update -q && sudo apt-get install -y -q tmux pigz
mkdir -p ~/bin
if [ ! -x ~/bin/micromamba ]; then
  base=https://github.com/mamba-org/micromamba-releases/releases/download/$MM_VER
  curl -sSLf -o ~/bin/micromamba "$base/micromamba-linux-64"
  echo "$(curl -sSLf "$base/micromamba-linux-64.sha256")  $HOME/bin/micromamba" | sha256sum -c -
  chmod +x ~/bin/micromamba
fi
export MAMBA_ROOT_PREFIX=~/mamba
[ -x ~/mamba/envs/c-gt/bin/python ] || ~/bin/micromamba create -y -q -f $C/vm/environment.yml
PY=~/mamba/envs/c-gt/bin/python
$PY -m pip install -q --no-deps cidre==0.0.1
~/bin/micromamba env export -n c-gt > $C/vm/environment.lock.yml
cd $C/experiments/c01_journal_graph
$PY c6_blocks.py --self-test
$PY test_c6_synthetic.py | tail -1
$PY cidre_toy_check.py --run-id cidre_toy_vm_$(date +%Y%m%d_%H%M%S) | tail -3
echo "setup OK. Next: put the two 'Copy as cURL' commands in ~/curl_edges.txt and ~/curl_pubs.txt, then bash ~/c/vm/download.sh"
