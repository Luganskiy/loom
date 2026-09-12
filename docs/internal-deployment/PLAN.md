# Loom internal deployment — implementation plan

Companion to [DESIGN.md](DESIGN.md). Phases are ordered by dependency; each has tasks, an exit criterion, and a rough effort. Effort assumes one person with AWS admin on the target account and familiarity with the repo's make targets.

Legend: `[ ]` open · `[x]` done · `[~]` optional

## Phase 0 — Decisions and prerequisites (½ day)

- [ ] Confirm the access path: corporate VPN/peering exists → use it; otherwise plan the subnet router (phase 5). Record the answer in DESIGN.md §5.3.
- [ ] Confirm the target VPC: reuse the platform VPC (private subnets in two AZs, NAT route present on those subnets) and note which private subnets host the ALB/tasks/RDS and which are designated for agent ENIs.
- [ ] Confirm region, Loom subdomain, and the parent hosted zone that will delegate it.
- [ ] Confirm the monthly budget figure for the AWS Budgets alarm (design estimate: $73, or $106 with a dedicated NAT).
- [ ] Create the SAM deployment bucket and the S3 access-logging bucket if the account does not have them.
- [ ] Decide whether the public hosted zone with a private-IP alias is acceptable (design default) or a private hosted zone is required (`[~]` task in phase 3).

**Exit:** every value in DESIGN.md Appendix A has a concrete answer written into `shared/etc/common.sh` (local, gitignored).

## Phase 1 — Fork changes (1–2 days)

Branch: `feat/internal-alb` in `github.com/Luganskiy/loom`. Keep every change parameter-driven or additive so upstream merges stay trivial.

- [x] `pAlbScheme` parameter on `shared/iac/infra.yaml`, default `internal`; wired through `shared/makefile` and env examples; docs updated.
- [ ] `frontend/iac/ecs.yaml`: task `NetworkConfiguration` → `AssignPublicIp: DISABLED`; rename or re-document the subnet parameter so it is fed private subnets (`frontend/etc/environment.sh.example`, `frontend/makefile`).
- [ ] `backend/iac/ecs.yaml` and `frontend/iac/ecs.yaml`: add `DeploymentConfiguration` with `DeploymentCircuitBreaker: {Enable: true, Rollback: true}`, `MinimumHealthyPercent: 100`, `MaximumPercent: 200`.
- [ ] `backend/iac/ecs.yaml`: `EnableExecuteCommand: true` on the service; add `ssmmessages:*Channel` actions to the task role; document the `aws ecs execute-command` invocation.
- [ ] `backend/iac/rds.yaml`: `pDeletionProtection` parameter (`true`/`false`, default `true`) → `DeletionProtection`; expose in `backend/makefile` and env example.
- [ ] `shared/iac/cognito.yaml`: `pCreateDemoUsers` parameter (default `false`) and a condition on every demo `UserPoolUser` / `UserPoolUserToGroupAttachment`; expose in `shared/makefile`.
- [ ] `[~]` `backend/iac/rds.yaml`: add `db.t4g.micro` / `db.t4g.small` to `pDbInstanceClass` allowed values.
- [ ] New `shared/iac/alarms.yaml`: parameters for ALB ARN suffix, target group ARN suffixes, cluster/service names, RDS identifier, notification email; resources: SNS topic + subscription, the alarms listed in DESIGN.md §11. Add `alarms.deploy` / `alarms.delete` targets to `shared/makefile` and the stack to `DEPLOYMENT.md`.
- [ ] `[~]` `shared/iac/dns.yaml` / `infra.yaml`: optional private hosted zone for the A alias (only if phase 0 requires it).
- [ ] Run `cfn-lint` on every touched template; run `checkov` if available; review the diff for secrets.
- [ ] Open a PR against the fork's `main`; merge after review. Tag `internal-v1`.

**Exit:** `main` of the fork deploys the internal topology with default parameters; `cfn-lint` clean; DEPLOYMENT.md reflects every new parameter and stack.

## Phase 2 — Environment configuration (½ day)

- [ ] Copy `shared/etc/common.sh.example` → `common.sh` and fill: profile, region, account, SAM bucket, VPC ID, private subnet IDs (both `PRIVATE_SUBNET_IDS` and `PUBLIC_SUBNET_IDS` = private IDs for the ALB), `ALB_INGRESS_CIDR`, `PUBLIC_FQDN`, `RDS_ALLOWED_CIDR`, Cognito names, artifact and logging buckets.
- [ ] `shared/etc/environment.sh`: `P_INFRA_ALB_SCHEME=internal`; tags.
- [ ] `backend/etc/environment.sh`: `P_ECS_BACKEND_CPU=512`, `_MEMORY=1024`, `_DESIRED_COUNT=1`; RDS class `db.t3.micro`, Multi-AZ `false`, proxy `false`, deletion protection `true`. The task's database URL comes from the RDS stack's secret, which uses the instance endpoint when the proxy is off.
- [ ] `frontend/etc/environment.sh`: `256` / `512` / `1`; private subnet IDs.
- [ ] Confirm all three env files are gitignored (`git check-ignore`).

**Exit:** `make -n` for each stack shows the intended parameter overrides; no real values in tracked files.

## Phase 3 — Foundation stacks (½ day, mostly waiting)

Order matters; each stack's outputs feed the next via `make outputs`.

1. [ ] `loom-dns` → delegate NS records in the parent zone; wait for resolution.
2. [ ] `loom-cognito` with `pCreateDemoUsers=false` → user pool, clients, groups. Create real operators in `t-admin`/`t-user` and the relevant `g-*` groups.
3. [ ] `loom-infra` with `pAlbScheme=internal` → verify: ALB scheme `internal`, nodes in the two private subnets, listener 443 only, certificate `ISSUED`, A record resolves to private IPs.
4. [ ] `loom-ecs-cluster`.
5. [ ] `loom-rds` → verify single-AZ, no proxy, deletion protection on, backups 7 days, not publicly accessible; capture `oRdsEndpoint`.
6. [ ] `loom-agent-sg` with the CIDR/SG rules agents need.
7. [ ] `loom-alarms` with the email subscription confirmed.
8. [ ] `[~]` `privatelink` only if a consuming VPC exists.

**Exit:** `make outputs` for `shared/` and `backend/` populates every `O_*` variable the service stacks need.

## Phase 4 — Build and deploy services (½ day)

- [ ] Build and push backend and frontend images (`make build` targets); confirm ECR scan results.
- [ ] Deploy the backend service; watch the deployment reach `COMPLETED`; `/health` healthy in the backend target group.
- [ ] Deploy the frontend service; `/` healthy in the frontend target group.
- [ ] From inside the VPC (ECS Exec, or a temporary instance): `curl -sk https://<fqdn>/health` and `https://<fqdn>/` return 200.
- [ ] Deliberately deploy a broken image tag once; confirm the circuit breaker rolls back and the alarm fires; redeploy the good tag.

**Exit:** both services stable at desired count 1 for 30 minutes; rollback proven.

## Phase 5 — Private access path (½ day)

Pick one, per phase 0.

- [ ] **Corporate VPN / peering:** ensure routes to the VPC CIDR and DNS resolution of the public hostname; `pAlbIngressCidr` covers the client range.
- [ ] **Subnet router:** launch a `t4g.nano` in a private subnet with SSM-only access, install the subnet router, advertise the VPC CIDR, approve routes; set `pAlbIngressCidr` to the VPC CIDR (traffic arrives from the router's private IP). Document the instance in the runbook.
- [ ] From an operator laptop: sign in, load the UI, deploy a test managed agent, invoke it, watch the SSE stream, delete it **with cleanup ticked**.

**Exit:** two operators can use Loom end-to-end from their normal workstations with no public endpoint involved.

## Phase 6 — Operations readiness (1 day)

- [ ] Restore test: create a manual snapshot, restore to a temporary instance, point a scratch backend at it (or verify tables), delete the temporary instance. Record time taken as the RTO.
- [ ] Runbooks under `docs/internal-deployment/runbooks/`: restore RDS; manual rollback; rotate RDS credential; ECS Exec; sync fork with upstream; delete an agent with cleanup.
- [ ] AWS Budgets alert at the agreed figure with the SNS topic.
- [ ] Verify log retention (30 days) and that ALB access logs land in the logging bucket.
- [ ] Optional CloudWatch dashboard (ALB 5xx/latency, task CPU/memory, RDS connections/storage).
- [ ] Cost check after the first full week against the estimate in DESIGN.md §10.

**Exit:** restore proven and timed; alarms observed firing at least once; budget alert live.

## Phase 7 — Agents in VPC mode (½ day)

- [ ] In Loom Settings → Networking create a VPC config profile with the agent subnets and `loom-agent-sg`.
- [ ] Deploy a managed (harness) agent with that profile; confirm the ENI appears in the designated subnet and the runtime reaches `READY`.
- [ ] Have the agent call one VPC-internal resource (an internal MCP server or HTTP endpoint) and one AWS API (a Bedrock model). Both must succeed, proving the private path and the NAT route.
- [ ] Register an internal MCP server in Loom and confirm tool discovery from the agent.
- [ ] `[~]` PrivateLink: deploy `privatelink.yaml`, create an interface endpoint in a consumer VPC, invoke the agent privately.

**Exit:** an agent in VPC mode reaches an internal resource and a model endpoint; documented in the design as verified.

## Phase 8 — Hardening and handover (½ day)

- [ ] IAM review of the backend task role: list every `Resource: "*"` and narrow where an ARN pattern exists.
- [ ] Confirm demo users are absent, MFA policy decided, Cognito advanced security settings reviewed.
- [ ] Security review of the fork diff (`/security-review` or equivalent); fix findings.
- [ ] Update the AgentCore atlas README (repo map and decision index) with the fork, the stacks, and the run cost.
- [ ] Schedule the monthly upstream merge; first merge performed and deployed.

**Exit:** design status moves from Draft to Accepted; atlas updated; owner named.

## Effort and cost summary

| Phase | Effort | Adds run cost |
|---|---|---|
| 0 Decisions | ½ day | — |
| 1 Fork changes | 1–2 days | — |
| 2 Env config | ½ day | — |
| 3 Foundation stacks | ½ day | ALB, RDS, KMS, Route 53 (~$37) |
| 4 Services | ½ day | Fargate (~$27) |
| 5 Access path | ½ day | $0 or ~$3 |
| 6 Ops readiness | 1 day | CloudWatch (~$4) |
| 7 Agents in VPC mode | ½ day | per-agent usage |
| 8 Hardening | ½ day | — |
| **Total** | **≈ 6 days** | **≈ $73/month** |

## Out of scope for this plan

- CI-driven deploys (the make targets are CI-ready; wiring Jenkins is a separate ticket).
- Multi-AZ or multi-task management plane.
- Federated identity providers.
- Migrating existing agents from the platform account into Loom's inventory (Loom imports by ARN; do it after phase 7 if wanted).
