# Internal deployment of Loom

Documentation for running the Loom management plane privately (internal ALB, existing platform VPC) at a small-team budget, with agents on Bedrock AgentCore Runtime in VPC network mode.

| Document | What it is |
|---|---|
| [DESIGN.md](DESIGN.md) | Design doc: goals, architecture, network, auth flow, data, agents in VPC mode, deployment, cost, operations, security, decisions, risks |
| [PLAN.md](PLAN.md) | Implementation plan in eight phases with tasks, exit criteria, effort and cost |
| [diagrams/](diagrams/) | AWS-style architecture diagrams (SVG + PNG) and the generator that produces them from the official AWS Architecture Icons |

## Diagrams at a glance

| | |
|---|---|
| ![architecture](diagrams/architecture.svg) | ![request flow](diagrams/request-flow.svg) |
| Target architecture | Request and authentication flow |
| ![agents in VPC mode](diagrams/agent-vpc-mode.svg) | ![deploy pipeline](diagrams/deploy-pipeline.svg) |
| Agents in VPC network mode and PrivateLink | Build and deploy pipeline |

## Relationship to upstream

This fork tracks `awslabs/loom`. The only functional change so far is the `pAlbScheme` parameter in `shared/iac/infra.yaml` (default `internal`). Everything else in the design is either an upstream parameter set to a leaner value or an additive template listed in PLAN.md phase 1. See the root [DEPLOYMENT.md](../../DEPLOYMENT.md) for the generic deployment procedure.
