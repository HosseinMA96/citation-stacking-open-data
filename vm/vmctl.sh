#!/usr/bin/env bash
# Laptop-side control of the Project C VM. Every command that changes billing is logged to vm/sessions.log.
#
#   vm/vmctl.sh create      create RG + VM (+ SSH from your IP only, auto-shutdown, self-deallocate role)
#   vm/vmctl.sh start       start (billing starts)
#   vm/vmctl.sh stop        DEALLOCATE (compute billing stops; the disk keeps billing)
#   vm/vmctl.sh status      power state and IP
#   vm/vmctl.sh ssh         ssh in
#   vm/vmctl.sh push        copy code (no data, no venv, no runs) to ~/c on the VM
#   vm/vmctl.sh fetch RUN   copy runs/RUN back to the laptop and verify SHA256SUMS
#   vm/vmctl.sh sendcurl    copy ~/curl_edges.txt and ~/curl_pubs.txt (your browser "Copy as cURL") to the VM, then delete them here
#   vm/vmctl.sh download    run download.sh on the VM in the background (log ~/download.log)
#   vm/vmctl.sh run RUN     start run_all.sh RUN in tmux on the VM (it deallocates the VM when done)
#   vm/vmctl.sh hours       VM hours and compute cost from sessions.log
#   vm/vmctl.sh delete      delete the whole resource group (asks you to type its name)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
C_ROOT="$(dirname "$HERE")"
[ -f "$HERE/vm.env" ] || { echo "copy vm/vm.env.example to vm/vm.env first"; exit 1; }
# shellcheck disable=SC1091
source "$HERE/vm.env"
LOG="$HERE/sessions.log"
PRICE_PER_H=$(case "$SIZE" in Standard_E8s_v5) echo 0.504;; Standard_E16s_v5) echo 1.008;; Standard_E8s_v6) echo 0.529;; Standard_E16s_v6) echo 1.058;; *) echo 0;; esac)

ip() { az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv; }
note() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1 $SIZE" >> "$LOG"; }

case "${1:-}" in
  create)
    MYIP=$(curl -s https://api.ipify.org)
    echo "Creating $SIZE in $LOCATION; SSH allowed only from $MYIP"
    az group create -n "$RG" -l "$LOCATION" --tags project=C -o none
    az vm create -g "$RG" -n "$VM" --image Ubuntu2404 --size "$SIZE" \
      --os-disk-size-gb "$DISK_GB" --storage-sku "$DISK_SKU" --disk-controller-type "${DISK_CONTROLLER:-SCSI}" \
      --admin-username "$ADMIN" --ssh-key-values "$SSH_PUB" \
      --public-ip-sku Standard --nsg-rule NONE --assign-identity '[system]' \
      --priority Regular --tags project=C -o none
    note start
    az network nsg rule create -g "$RG" --nsg-name "${VM}NSG" -n ssh-from-my-ip --priority 1000 \
      --source-address-prefixes "$MYIP/32" --destination-port-ranges 22 --protocol Tcp --access Allow -o none
    az vm auto-shutdown -g "$RG" -n "$VM" --time "$AUTO_SHUTDOWN_UTC" -o none
    # Let the VM deallocate itself (and nothing else) when the run ends.
    PRINCIPAL=$(az vm show -g "$RG" -n "$VM" --query identity.principalId -o tsv)
    VMID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
    az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
      --role "Virtual Machine Contributor" --scope "$VMID" -o none
    echo "VM up at $(ip). Next: vm/vmctl.sh push, then vm/vmctl.sh ssh and run ~/c/vm/setup_vm.sh"
    ;;
  start)  az vm start -g "$RG" -n "$VM" -o none; note start; echo "running at $(ip)" ;;
  stop)   az vm deallocate -g "$RG" -n "$VM" -o none; note stop; echo "deallocated" ;;
  status) az vm get-instance-view -g "$RG" -n "$VM" --query "instanceView.statuses[1].displayStatus" -o tsv; ip ;;
  ssh)    ssh -o ServerAliveInterval=60 "$ADMIN@$(ip)" ;;
  push)
    rsync -az --info=stats1 --exclude '.venv/' --exclude 'data/' --exclude 'runs/' --exclude '__pycache__/' \
      --exclude 'vm/sessions.log' --exclude 'paper/' --exclude 'lit/' \
      "$C_ROOT/" "$ADMIN@$(ip):c/"
    ;;
  fetch)
    RUN="${2:?usage: vmctl.sh fetch RUN_ID}"
    DEST="$C_ROOT/experiments/c01_journal_graph/runs/$RUN"
    [ -e "$DEST" ] && { echo "$DEST exists locally; never overwrite a run"; exit 1; }
    rsync -az --info=progress2 "$ADMIN@$(ip):c/experiments/c01_journal_graph/runs/$RUN/" "$DEST/"
    (cd "$DEST" && sha256sum -c SHA256SUMS)
    ;;
  sendcurl)
    for f in curl_edges.txt curl_pubs.txt; do [ -f ~/$f ] || { echo "missing ~/$f"; exit 1; }; done
    scp -q ~/curl_edges.txt ~/curl_pubs.txt "$ADMIN@$(ip):"
    ssh "$ADMIN@$(ip)" 'chmod 600 ~/curl_edges.txt ~/curl_pubs.txt'
    shred -u ~/curl_edges.txt ~/curl_pubs.txt 2>/dev/null || rm -f ~/curl_edges.txt ~/curl_pubs.txt
    echo "sent; local copies deleted. Next: vm/vmctl.sh download"
    ;;
  download)
    ssh "$ADMIN@$(ip)" 'nohup bash -c "bash ~/c/vm/download.sh; echo DOWNLOAD_EXIT=\$?" > ~/download.log 2>&1 < /dev/null & echo started; echo "watch: ssh in and tail -f ~/download.log"'
    ;;
  run)
    RUN="${2:?usage: vmctl.sh run RUN_ID}"
    ssh "$ADMIN@$(ip)" "tmux new -d -s run 'bash ~/c/vm/run_all.sh $RUN' && echo started tmux session 'run'"
    ;;
  hours)
    python3 - "$LOG" "$PRICE_PER_H" <<'EOF'
import sys, datetime as dt
log, price = sys.argv[1], float(sys.argv[2])
total, start = 0.0, None
for line in open(log):
    ts, ev = line.split()[:2]
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ev == "start" and start is None: start = t
    elif ev == "stop" and start is not None: total += (t - start).total_seconds() / 3600; start = None
running = " (VM still running: add the time since the last start)" if start else ""
print(f"logged VM hours: {total:.2f}; compute ~${total * price:.2f} at ${price}/h{running}")
print("auto-shutdown and self-deallocation are not logged here; check Cost Management for the exact bill")
EOF
    ;;
  delete)
    read -r -p "Type the resource group name ($RG) to delete it and everything in it: " ans
    [ "$ans" = "$RG" ] || { echo "not deleted"; exit 1; }
    az group delete -n "$RG" --yes --no-wait; note delete; echo "deletion started"
    ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
