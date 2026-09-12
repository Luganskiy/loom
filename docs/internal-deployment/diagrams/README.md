# Architecture diagrams

Four diagrams in the style of AWS documentation, built from the official [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) (release 2026-01-30, consumed via the `aws-icons` npm package). SVGs are self-contained (icons inlined); PNGs are 2× exports for slides and chat.

| File | Shows |
|---|---|
| `architecture.svg` / `.png` | Target architecture: corporate network → internal ALB → Fargate tasks → RDS; NAT egress to regional services; agent runtime ENI in VPC mode |
| `request-flow.svg` / `.png` | One browser session: Cognito sign-in, DNS, private path to the ALB, path routing, JWT verification, RDS, AgentCore SSE stream |
| `agent-vpc-mode.svg` / `.png` | Agent in VPC network mode reaching internal resources, egress via the VPC, PrivateLink ingress for other VPCs |
| `deploy-pipeline.svg` / `.png` | Build, push, `sam deploy`, ECS rolling update with circuit breaker, alarms |

## Regenerate

```bash
npm install --prefix /tmp/icons aws-icons@3.3.0
python3 gen_diagrams.py --icons /tmp/icons/node_modules/aws-icons/icons --out . --png
```

`--png` needs `rsvg-convert` (librsvg). Layout is hand-placed in `gen_diagrams.py`; edit coordinates there, not the SVGs.

Conventions follow the AWS icon deck: AWS Cloud (dark solid), Region (teal dashed), VPC (purple solid), Availability Zone (teal dashed), private subnet (teal, tinted), public subnet (green, tinted), corporate network (grey). Solid arrows are private traffic; dashed arrows go to public AWS endpoints or are AgentCore service calls. Numbered badges mark the flow described in DESIGN.md.
