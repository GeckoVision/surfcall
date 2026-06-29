#!/usr/bin/env bash
# =============================================================================
# surfcall — one-time AWS cleanup of orphaned / junk CloudFormation stacks.
#
# FOUNDER-RUN. Claude cannot (and must not) execute destructive AWS ops; this
# script exists so YOU run it after eyeballing exactly what it will delete.
#
#   ./infra/cleanup-orphaned-stacks.sh            # interactive, asks to confirm
#   ./infra/cleanup-orphaned-stacks.sh --yes      # skip the typed confirmation
#
# Reclaims ~$110/mo (2 idle NAT gateways + 2 idle ALBs + their EIPs) by tearing
# down two orphaned VPC stacks and three stuck/failed junk stacks.
#
# Safety: PROTECT is a hard allowlist of stacks that must NEVER be deleted. If
# any DELETE target ever appears in PROTECT, the script aborts before touching
# anything. Each VPC stack delete cascades NAT/ALB/EIP/subnets/ECS with it.
# =============================================================================
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-2}"

# Live stacks — NEVER delete. (api.geckovision.tech + the agent service.)
PROTECT=(
  "gecko-api-ecs"
  "gecko-agent-ecs"
)

# The five stacks to remove. Confirmed orphaned (ALB 0 targets, no workload)
# or stuck (REVIEW_IN_PROGRESS changeset / CREATE_FAILED).
DELETE=(
  "geckovision-ecs"                                 # orphaned VPC stack
  "gecko-campaign-api-ecs"                          # orphaned VPC stack
  "gecko-api"                                       # junk — stuck REVIEW_IN_PROGRESS
  "geckovision-cloudmap-test"                       # junk — stuck REVIEW_IN_PROGRESS
  "Infra-ECS-Cluster-swift-parrot-o5usi9-dfab9047"  # junk — CREATE_FAILED
)

AUTO_YES=false
[[ "${1:-}" == "--yes" ]] && AUTO_YES=true

# --- Defense in depth: a protected stack must never be in the delete list. ---
for d in "${DELETE[@]}"; do
  for p in "${PROTECT[@]}"; do
    if [[ "$d" == "$p" ]]; then
      echo "FATAL: '$d' is in the PROTECT list. Aborting — deleting nothing." >&2
      exit 1
    fi
  done
done

echo "==> Region: $REGION"
echo "==> Will PROTECT (never touched): ${PROTECT[*]}"
echo ""
echo "==> Will DELETE these ${#DELETE[@]} stacks:"
for s in "${DELETE[@]}"; do
  status=$(aws cloudformation describe-stacks --stack-name "$s" --region "$REGION" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  printf "    - %-50s [%s]\n" "$s" "$status"
done
echo ""

if [[ "$AUTO_YES" != true ]]; then
  read -r -p "Type DELETE to tear these down (anything else aborts): " reply
  if [[ "$reply" != "DELETE" ]]; then
    echo "Aborted — nothing deleted."
    exit 0
  fi
fi

# Fire all deletes (independent stacks → safe to run concurrently), then wait.
echo ""
for s in "${DELETE[@]}"; do
  echo "==> delete-stack $s"
  aws cloudformation delete-stack --stack-name "$s" --region "$REGION" || \
    echo "    (delete-stack call failed for $s — continuing)"
done

echo ""
echo "==> Waiting for deletes to complete (NAT/VPC teardown ~3-5 min each)..."
for s in "${DELETE[@]}"; do
  if aws cloudformation wait stack-delete-complete --stack-name "$s" --region "$REGION" 2>/dev/null; then
    echo "    ✓ $s deleted"
  else
    # A stuck VPC delete usually means a leftover ENI/ALB held a subnet.
    final=$(aws cloudformation describe-stacks --stack-name "$s" --region "$REGION" \
      --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "GONE")
    if [[ "$final" == "GONE" ]]; then
      echo "    ✓ $s deleted"
    else
      echo "    ✗ $s did NOT delete cleanly — status: $final (check the console for the blocking resource)"
    fi
  fi
done

echo ""
echo "==> Remaining stacks:"
aws cloudformation list-stacks --region "$REGION" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE REVIEW_IN_PROGRESS CREATE_FAILED \
  --query 'sort_by(StackSummaries,&StackName)[].{Name:StackName,Status:StackStatus}' \
  --output table
echo ""
echo "Done. The two protected stacks (gecko-api-ecs, gecko-agent-ecs) are untouched."
