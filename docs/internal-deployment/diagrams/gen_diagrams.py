#!/usr/bin/env python3
"""Generate the internal-deployment architecture diagrams as self-contained SVGs.

The diagrams follow the AWS Architecture Icons conventions (group borders,
service/resource icons, labels) so they read like the diagrams in AWS
documentation. Icons are inlined from the official AWS Architecture Icons set
(https://aws.amazon.com/architecture/icons/), consumed via the `aws-icons` npm
package, so the output SVGs have no external dependencies.

Usage:
    npm install aws-icons@3.3.0          # anywhere, e.g. /tmp/icons
    python3 gen_diagrams.py --icons /tmp/icons/node_modules/aws-icons/icons --out .
    # optional PNG export (needs librsvg): --png

The layout is hand-placed; every coordinate is in the diagram functions below.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

# --- AWS Architecture Icons deck conventions ---------------------------------
FONT = "Amazon Ember, Arial, Helvetica, sans-serif"
TEXT = "#16191F"
MUTED = "#545B64"
ARROW = "#545B64"

GROUP_STYLES: dict[str, dict] = {
    "cloud": dict(stroke="#242F3E", dash=None, fill="none", icon=("architecture-group", "AWSCloud")),
    "region": dict(stroke="#00A4A6", dash="6,4", fill="none", icon=("architecture-group", "Region")),
    "vpc": dict(stroke="#8C4FFF", dash=None, fill="none", icon=("architecture-group", "VirtualprivatecloudVPC")),
    "az": dict(stroke="#00A4A6", dash="6,4", fill="none", icon=None),
    "private_subnet": dict(stroke="#00A4A6", dash=None, fill="#E6F6F7", icon=("architecture-group", "Privatesubnet")),
    "public_subnet": dict(stroke="#7AA116", dash=None, fill="#F2F6E8", icon=("architecture-group", "Publicsubnet")),
    "corp": dict(stroke="#7D8998", dash=None, fill="none", icon=("architecture-group", "Corporatedatacenter")),
    "generic": dict(stroke="#7D8998", dash="6,4", fill="none", icon=None),
    "account": dict(stroke="#E7157B", dash=None, fill="none", icon=("architecture-group", "AWSAccount")),
}


class Icons:
    """Loads official icon SVGs and returns them as inline <svg> fragments."""

    def __init__(self, root: str):
        self.root = root
        self._cache: dict[str, tuple[str, str]] = {}

    def _load(self, folder: str, name: str) -> tuple[str, str]:
        key = f"{folder}/{name}"
        if key in self._cache:
            return self._cache[key]
        path = os.path.join(self.root, folder, f"{name}.svg")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        m = re.search(r'viewBox="([^"]+)"', raw)
        viewbox = m.group(1) if m else "0 0 64 64"
        inner = re.sub(r"^.*?<svg[^>]*>", "", raw, count=1, flags=re.S)
        inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
        inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
        self._cache[key] = (viewbox, inner.strip())
        return self._cache[key]

    def svg(self, folder: str, name: str, x: float, y: float, size: float) -> str:
        viewbox, inner = self._load(folder, name)
        return (
            f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{viewbox}" '
            f'role="img" aria-label="{name}">{inner}</svg>'
        )


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Canvas:
    width: int
    height: int
    icons: Icons
    title: str
    parts: list[str] = field(default_factory=list)

    # -- primitives -----------------------------------------------------------
    def group(self, style: str, x: float, y: float, w: float, h: float, label: str,
              sublabel: Optional[str] = None) -> None:
        st = GROUP_STYLES[style]
        dash = f' stroke-dasharray="{st["dash"]}"' if st["dash"] else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{st["fill"]}" '
            f'stroke="{st["stroke"]}" stroke-width="1.25"{dash}/>'
        )
        tx = x + 8
        if st["icon"]:
            self.parts.append(self.icons.svg(st["icon"][0], st["icon"][1], x, y, 28))
            tx = x + 34
        self.parts.append(
            f'<text x="{tx}" y="{y + 19}" font-family="{FONT}" font-size="13" '
            f'fill="{st["stroke"] if style in ("az",) else TEXT}">{esc(label)}</text>'
        )
        if sublabel:
            self.parts.append(
                f'<text x="{tx}" y="{y + 34}" font-family="{FONT}" font-size="11" '
                f'fill="{MUTED}">{esc(sublabel)}</text>'
            )

    def icon(self, folder: str, name: str, cx: float, cy: float, label: str,
             size: float = 48, sublabel: Optional[str] = None) -> tuple[float, float]:
        """Place an icon centred at (cx, cy) with a label under it. Returns centre."""
        x, y = cx - size / 2, cy - size / 2
        self.parts.append(self.icons.svg(folder, name, x, y, size))
        lines = label.split("\n")
        ty = y + size + 14
        for i, line in enumerate(lines):
            weight = "600" if i == 0 else "400"
            colour = TEXT if i == 0 else MUTED
            fs = 12 if i == 0 else 11
            self.parts.append(
                f'<text x="{cx}" y="{ty + i * 13}" text-anchor="middle" font-family="{FONT}" '
                f'font-size="{fs}" font-weight="{weight}" fill="{colour}">{esc(line)}</text>'
            )
        return cx, cy

    def text(self, x: float, y: float, s: str, size: int = 11, colour: str = MUTED,
             anchor: str = "start", italic: bool = False, bold: bool = False) -> None:
        style = ' font-style="italic"' if italic else ""
        weight = ' font-weight="600"' if bold else ""
        for i, line in enumerate(s.split("\n")):
            self.parts.append(
                f'<text x="{x}" y="{y + i * (size + 3)}" text-anchor="{anchor}" font-family="{FONT}" '
                f'font-size="{size}" fill="{colour}"{style}{weight}>{esc(line)}</text>'
            )

    def arrow(self, points: list[tuple[float, float]], label: Optional[str] = None,
              num: Optional[int] = None, dashed: bool = False, bidir: bool = False,
              label_at: float = 0.5, label_dy: float = -6, colour: str = ARROW,
              label_dx: float = 14) -> None:
        d = "M " + " L ".join(f"{px},{py}" for px, py in points)
        dash = ' stroke-dasharray="5,4"' if dashed else ""
        start = ' marker-start="url(#arrowhead-rev)"' if bidir else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.5"{dash} '
            f'marker-end="url(#arrowhead)"{start}/>'
        )
        if label or num is not None:
            # place label on the polyline at fraction label_at of total length
            total = sum(((points[i + 1][0] - points[i][0]) ** 2 + (points[i + 1][1] - points[i][1]) ** 2) ** 0.5
                        for i in range(len(points) - 1))
            target, acc = total * label_at, 0.0
            lx, ly = points[-1]
            for i in range(len(points) - 1):
                (x1, y1), (x2, y2) = points[i], points[i + 1]
                seg = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                if acc + seg >= target:
                    t = (target - acc) / seg if seg else 0
                    lx, ly = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    break
                acc += seg
            if num is not None:
                self.parts.append(
                    f'<circle cx="{lx}" cy="{ly}" r="9" fill="#232F3E" stroke="#fff" stroke-width="1.5"/>'
                    f'<text x="{lx}" y="{ly + 3.5}" text-anchor="middle" font-family="{FONT}" '
                    f'font-size="10" font-weight="700" fill="#fff">{num}</text>'
                )
                lx += label_dx
                anchor = "start" if label_dx >= 0 else "end"
            else:
                anchor = "middle"
            if label:
                for i, line in enumerate(label.split("\n")):
                    self.parts.append(
                        f'<text x="{lx}" y="{ly + label_dy + i * 12}" text-anchor="{anchor}" '
                        f'font-family="{FONT}" font-size="10.5" fill="{TEXT}" '
                        f'style="paint-order:stroke" stroke="#fff" stroke-width="3">{esc(line)}</text>'
                    )

    def legend(self, x: float, y: float, items: list[tuple[str, str]]) -> None:
        """items: (kind, text) where kind in solid|dashed."""
        for i, (kind, txt) in enumerate(items):
            ly = y + i * 18
            dash = ' stroke-dasharray="5,4"' if kind == "dashed" else ""
            self.parts.append(
                f'<path d="M {x},{ly} L {x + 28},{ly}" stroke="{ARROW}" stroke-width="1.5"{dash} '
                f'marker-end="url(#arrowhead)"/>'
            )
            self.text(x + 36, ly + 4, txt, size=11, colour=TEXT)

    # -- output ---------------------------------------------------------------
    def render(self) -> str:
        defs = (
            '<defs>'
            '<marker id="arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" '
            'markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill="#545B64"/></marker>'
            '<marker id="arrowhead-rev" markerWidth="8" markerHeight="8" refX="1" refY="4" orient="auto" '
            'markerUnits="userSpaceOnUse"><path d="M8,0 L0,4 L8,8 z" fill="#545B64"/></marker>'
            '</defs>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" font-family="{FONT}">'
            f'<title>{esc(self.title)}</title>{defs}'
            f'<rect width="{self.width}" height="{self.height}" fill="#ffffff"/>'
            + "".join(self.parts) + "</svg>"
        )


# --- Diagram 1: target architecture -------------------------------------------

def diagram_architecture(ic: Icons) -> Canvas:
    c = Canvas(1460, 990, ic, "Loom internal deployment – target architecture")
    c.text(20, 28, "Loom for AWS — internal deployment, target architecture", size=16, colour=TEXT, bold=True)
    c.text(20, 46, "Management plane on ECS Fargate behind an internal ALB inside the existing platform VPC; "
                   "agents on Amazon Bedrock AgentCore Runtime in VPC network mode.", size=11)

    # Corporate side -----------------------------------------------------------
    c.group("corp", 20, 310, 210, 290, "Corporate network")
    c.icon("resource", "Users", 125, 380, "Operators\nbrowser, any OS")
    c.icon("resource", "AmazonVPCVPNConnection", 125, 500, "Private connectivity\nVPN, peering or subnet router", 40)

    # AWS Cloud / Region / VPC ---------------------------------------------------
    c.group("cloud", 270, 70, 1170, 850, "AWS Cloud")
    c.icon("resource", "AmazonRoute53HostedZone", 380, 130, "Route 53 public hosted zone\nA alias → ALB (private IPs)", 40)
    c.group("region", 290, 200, 1130, 700, "Region", "same region as the AgentCore platform")

    c.group("vpc", 310, 240, 650, 640, "Existing platform VPC", "reused: subnets, NAT and IGW already exist")
    c.icon("resource", "ElasticLoadBalancingApplicationLoadBalancer", 635, 300,
           "Application Load Balancer\ninternal · HTTPS 443 · TLS 1.3 · nodes in both AZs")

    # AZ a ---------------------------------------------------------------------
    c.group("az", 330, 380, 300, 480, "Availability Zone a")
    c.group("private_subnet", 345, 405, 270, 440, "Private subnet")
    c.icon("architecture-service", "AWSFargate", 410, 480, "Frontend service\nECS Fargate · nginx · :8000")
    c.icon("architecture-service", "AWSFargate", 545, 480, "Backend service\nECS Fargate · FastAPI · :8000")
    c.icon("resource", "AmazonAuroraPostgreSQLInstance", 480, 640, "RDS for PostgreSQL\nsingle-AZ · gp3 · 7-day backups · :5432")
    c.text(360, 785, "ECS may place tasks in either private subnet.\nRDS subnet group spans both AZs.", size=10, italic=True)

    # AZ b ---------------------------------------------------------------------
    c.group("az", 650, 380, 290, 480, "Availability Zone b")
    c.group("public_subnet", 665, 405, 260, 100, "Public subnet")
    c.icon("resource", "AmazonVPCNATGateway", 720, 452, "NAT gateway (existing)", 40)
    c.icon("resource", "AmazonVPCInternetGateway", 960, 452, "Internet\ngateway", 40)
    c.group("private_subnet", 665, 525, 260, 320, "Private subnet")
    c.icon("resource", "AmazonVPCElasticNetworkInterface", 795, 610, "Agent runtime ENI\nAgentCore VPC network mode", 40)
    c.text(680, 700, "Agent security group\n(security_group.yaml):\n443 · 80 · 3000 (MCP) · 8080 (A2A)\nfrom allowed CIDR / SG", size=10, italic=True)

    # Regional services --------------------------------------------------------
    c.group("generic", 985, 240, 420, 650, "Regional AWS services", "public endpoints, reached through the NAT gateway:")
    c.text(1019, 288, "AgentCore deploy + invoke (SSE), Bedrock, Secrets Manager,\nS3, CloudWatch, Cognito JWKS, ECR image pulls", size=10)
    c.icon("architecture-service", "AmazonBedrockAgentCore", 1080, 345, "Bedrock AgentCore\nRuntime · Memory · Gateway · Identity")
    c.icon("architecture-service", "AmazonCognito", 1300, 345, "Amazon Cognito\nuser pool · groups · JWT\nJWKS fetched by the backend")
    c.icon("architecture-service", "AmazonBedrock", 1080, 460, "Amazon Bedrock\nmodels · CountTokens")
    c.icon("architecture-service", "AmazonElasticContainerRegistry", 1300, 460, "Amazon ECR\nfrontend + backend images")
    c.icon("architecture-service", "AWSSecretsManager", 1080, 590, "Secrets Manager\nDB credentials · LiteLLM key")
    c.icon("architecture-service", "AmazonCloudWatch", 1300, 590, "CloudWatch\nlogs · alarms · Container Insights")
    c.icon("architecture-service", "AmazonSimpleStorageService", 1080, 720, "S3 artifact bucket\nagent code bundles · ALB logs")
    c.icon("architecture-service", "AWSCertificateManager", 1300, 720, "ACM certificate\nDNS-validated via Route 53")
    c.icon("architecture-service", "AWSKeyManagementService", 1080, 830, "KMS CMKs\nECR · secrets · log groups", 40)
    c.icon("architecture-service", "AWSIdentityandAccessManagement", 1300, 830, "IAM\ntask, execution, agent roles", 40)

    # Flows --------------------------------------------------------------------
    # 1 sign-in: browser -> Cognito over the internet (public endpoint)
    c.arrow([(125, 340), (125, 104), (1300, 104), (1300, 321)], num=1, dashed=True,
            label="Sign-in (InitiateAuth, USER_PASSWORD_AUTH) over the internet → ID + access JWT", label_at=0.45)
    # 2 DNS
    c.arrow([(140, 356), (140, 270), (282, 270), (282, 130), (358, 130)], num=2, dashed=True,
            label="DNS lookup\nloom.example.com", label_at=0.3, label_dy=-10)
    c.arrow([(402, 130), (660, 130), (660, 276)], dashed=True, label="alias → private IPs", label_at=0.4)
    # 3 HTTPS via private connectivity
    c.arrow([(150, 500), (250, 500), (250, 300), (605, 300)], num=3,
            label="HTTPS 443 from the allowed CIDR (pAlbIngressCidr)", label_at=0.62)
    # 4 path routing
    c.arrow([(620, 326), (430, 452)], num=4, label="/ (default)", label_at=0.5, label_dy=-8)
    c.arrow([(640, 326), (560, 452)], label="/api/* · /health", label_at=0.55, label_dy=12)
    # 5 DB
    c.arrow([(545, 508), (500, 612)], num=5, label="PostgreSQL 5432\nSG: backend only", label_at=0.5)
    # 6 AWS APIs via NAT
    c.arrow([(575, 480), (640, 480), (640, 452), (696, 452)], num=6, label_at=0.2, label_dy=16,
            label="AWS API calls (SigV4)\nECR image pulls")
    c.arrow([(744, 452), (936, 452)], label="egress", label_at=0.5)
    c.arrow([(984, 452), (992, 452)], dashed=True)
    # 7 agent runtime ENI provisioned by AgentCore
    c.arrow([(1056, 345), (1010, 345), (1010, 540), (795, 540), (795, 588)], dashed=True, num=7,
            label="provisions ENI in the private subnet\nnetworkMode = VPC (subnets + SG)", label_at=0.86, label_dy=16)

    # Legend
    c.legend(300, 950, [("solid", "Private traffic inside the VPC / via private connectivity"),
                        ("dashed", "Traffic to public AWS endpoints (Cognito, DNS, AWS APIs via NAT)")])
    return c


# --- Diagram 2: request and authentication flow ------------------------------

def diagram_request_flow(ic: Icons) -> Canvas:
    c = Canvas(1460, 640, ic, "Loom internal deployment – request and authentication flow")
    c.text(20, 28, "Request and authentication flow", size=16, colour=TEXT, bold=True)
    c.text(20, 46, "One browser session from sign-in to a streamed agent response. Solid = private path; dashed = public AWS endpoint.", size=11)

    c.group("corp", 20, 110, 260, 320, "Corporate network")
    c.icon("resource", "Client", 90, 200, "Browser\nSPA (React)")
    c.icon("resource", "AmazonVPCVPNConnection", 200, 330, "Private\nconnectivity", 40)

    c.group("cloud", 320, 95, 1120, 480, "AWS Cloud")
    c.icon("architecture-service", "AmazonCognito", 480, 170, "Amazon Cognito\ncognito-idp public endpoint")
    c.icon("resource", "AmazonRoute53HostedZone", 480, 470, "Route 53\nA alias record", 40)

    c.group("vpc", 560, 130, 660, 410, "Platform VPC")
    c.icon("resource", "ElasticLoadBalancingApplicationLoadBalancer", 640, 330, "Internal ALB\nHTTPS 443")
    c.group("private_subnet", 740, 160, 460, 360, "Private subnets")
    c.icon("architecture-service", "AWSFargate", 840, 230, "Frontend\nnginx · static SPA")
    c.icon("architecture-service", "AWSFargate", 1040, 230, "Backend\nFastAPI · JWT check")
    c.icon("resource", "AmazonAuroraPostgreSQLInstance", 1120, 450, "RDS PostgreSQL\nagent metadata")

    c.icon("architecture-service", "AmazonBedrockAgentCore", 1330, 230, "AgentCore Runtime\nagent invocation")
    c.icon("architecture-service", "AmazonBedrock", 1330, 450, "Amazon Bedrock\nmodel inference")

    c.arrow([(90, 160), (90, 75), (480, 75), (480, 146)], num=1, dashed=True,
            label="InitiateAuth (USER_PASSWORD_AUTH) → ID + access token", label_at=0.5, label_dy=-8)
    c.arrow([(90, 275), (90, 470), (456, 470)], num=2, dashed=True,
            label="resolve loom.example.com → private IP of the ALB", label_at=0.62, label_dy=-8)
    c.arrow([(114, 215), (200, 215), (200, 310)], num=3, label="HTTPS", label_at=0.3, label_dy=-8)
    c.arrow([(220, 330), (614, 330)], label="allowed CIDR only (pAlbIngressCidr)", label_at=0.5, label_dy=-8)
    c.arrow([(640, 306), (640, 230), (816, 230)], num=4, label="GET / → SPA assets", label_at=0.55, label_dy=-8)
    c.arrow([(652, 330), (960, 330), (960, 230), (1016, 230)], num=5, bidir=True,
            label="/api/* with Authorization: Bearer <JWT>\nSSE relayed back to the browser", label_at=0.2, label_dy=-8)
    c.arrow([(1030, 206), (1030, 110), (500, 110), (500, 146)], num=6, dashed=True,
            label="fetch JWKS; verify signature, issuer, audience, groups", label_at=0.5, label_dy=16)
    c.arrow([(1064, 240), (1120, 240), (1120, 426)], num=7, label="read / write agent records", label_at=0.75, label_dx=-14)
    c.arrow([(1064, 222), (1306, 222)], num=8, dashed=True, bidir=True, label="InvokeAgentRuntime\nSSE stream", label_at=0.55, label_dy=-20, label_dx=-14)
    c.arrow([(1330, 254), (1330, 426)], dashed=True, label="Converse / InvokeModel", label_at=0.5, label_dx=-14)

    c.legend(340, 600, [("solid", "Private path (VPN → internal ALB → tasks → RDS)"),
                        ("dashed", "Public AWS endpoints (Cognito, Route 53, AgentCore, Bedrock via NAT)")])
    return c


# --- Diagram 3: agents in VPC network mode + PrivateLink ingress ---------------

def diagram_agent_vpc(ic: Icons) -> Canvas:
    c = Canvas(1460, 670, ic, "Loom internal deployment – agents in VPC network mode")
    c.text(20, 28, "Agents in VPC network mode and PrivateLink ingress", size=16, colour=TEXT, bold=True)
    c.text(20, 46, "How a Loom-managed agent reaches private resources, and how private consumers reach the agent. "
                   "Loom's own tasks are omitted for clarity.", size=11)

    c.group("cloud", 20, 70, 1420, 540, "AWS Cloud")
    c.icon("architecture-service", "AWSFargate", 120, 200, "Loom backend\ndeploys and invokes agents")
    c.icon("architecture-service", "AmazonBedrockAgentCore", 120, 440, "AgentCore control plane\nCreateAgentRuntime")

    c.group("vpc", 280, 110, 700, 480, "Platform VPC", "same VPC as the Loom management plane")
    c.group("private_subnet", 300, 150, 320, 420, "Private subnet (agent-designated)")
    c.icon("resource", "AmazonVPCElasticNetworkInterface", 400, 270, "Agent runtime ENI\nowned by AgentCore, in your subnet")
    c.icon("resource", "Shield", 540, 270, "Agent security group\nloom-agent-sg stack", 40)
    c.icon("resource", "ElasticLoadBalancingNetworkLoadBalancer", 400, 450, "Internal NLB\nprivatelink.yaml")
    c.icon("resource", "AmazonVPCEndpoints", 540, 450, "VPC Endpoint Service\nno acceptance required", 40)

    c.group("private_subnet", 640, 150, 320, 420, "Private subnet (workloads)")
    c.icon("resource", "Server", 740, 270, "Internal MCP servers\ninternal APIs", 40)
    c.icon("resource", "AmazonAuroraPostgreSQLInstance", 880, 270, "Internal data\nRDS, caches", 40)
    c.icon("resource", "AmazonVPCNATGateway", 790, 440, "NAT gateway\nor VPC endpoints", 40)

    c.group("generic", 1010, 110, 410, 480, "Outside the platform VPC")
    c.icon("architecture-service", "AmazonBedrock", 1120, 220, "Amazon Bedrock\nand other AWS endpoints")
    c.icon("architecture-service", "AmazonBedrockAgentCore", 1310, 220, "AgentCore Memory,\nGateway, Identity")
    c.icon("resource", "Servers", 1210, 440, "Consumers in other VPCs\ninvoke via interface endpoint", 40)

    c.arrow([(150, 200), (200, 200), (200, 270), (376, 270)], num=1, dashed=True,
            label="InvokeAgentRuntime (SSE) via the AgentCore data plane", label_at=0.2, label_dy=-8)
    c.arrow([(120, 270), (120, 412)], num=2, dashed=True,
            label="networkMode = VPC\nsubnets + SG (from Loom\nSettings → Networking)", label_at=0.5)
    c.arrow([(150, 440), (230, 440), (230, 300), (376, 286)], num=3, dashed=True,
            label="provisions ENI", label_at=0.15, label_dy=-8)
    c.arrow([(424, 270), (516, 270)], label="ingress rules", label_at=0.5, label_dy=-6)
    c.arrow([(564, 270), (716, 270)], num=4, label="private calls", label_at=0.25, label_dy=-8)
    c.arrow([(424, 282), (600, 340), (856, 290)])
    c.arrow([(424, 290), (640, 440), (766, 440)], num=5, label="outbound to AWS APIs\nand model endpoints", label_at=0.35, label_dy=14)
    c.arrow([(814, 440), (990, 440), (990, 220), (1096, 220)], dashed=True, label="egress via the VPC", label_at=0.5, label_dx=-14)
    c.arrow([(1186, 440), (1150, 440), (1150, 520), (612, 520), (612, 450), (564, 450)], num=6,
            label="PrivateLink: interface endpoint → endpoint service", label_at=0.5, label_dy=-8)
    c.arrow([(516, 450), (424, 450)])
    c.arrow([(400, 426), (400, 294)], label="NLB targets\nthe agent port", label_at=0.5, label_dx=-10)

    c.legend(40, 630, [("solid", "Traffic that stays private (inside the VPC or over PrivateLink)"),
                       ("dashed", "AgentCore service calls and egress to AWS endpoints")])
    return c


# --- Diagram 4: build and deployment pipeline --------------------------------

def diagram_pipeline(ic: Icons) -> Canvas:
    c = Canvas(1460, 400, ic, "Loom internal deployment – build and deploy pipeline")
    c.text(20, 28, "Build and deploy pipeline", size=16, colour=TEXT, bold=True)
    c.text(20, 46, "Every step is an existing make target; the plan adds the deployment guards and alarms. "
                   "No public endpoints are touched at any stage.", size=11)

    c.icon("resource", "User", 90, 170, "Operator\nmake targets")
    c.icon("resource", "GitRepository", 270, 170, "Fork of awslabs/loom\nbranch feat/internal-alb", 40)
    c.icon("resource", "Document", 180, 300, "etc/common.sh · etc/environment.sh\nparameters for every stack", 40)

    c.group("cloud", 360, 80, 1080, 300, "AWS Cloud")
    c.icon("architecture-service", "AmazonElasticContainerRegistry", 450, 170, "Amazon ECR\npodman build + push")
    c.icon("architecture-service", "AWSCloudFormation", 640, 170, "CloudFormation / SAM\nsam deploy per stack")
    c.icon("architecture-service", "AmazonElasticContainerService", 830, 170, "ECS service\nrolling update, circuit breaker")
    c.icon("resource", "ElasticLoadBalancingApplicationLoadBalancer", 1020, 170, "Internal ALB\nhealth checks / and /health")
    c.icon("architecture-service", "AmazonCloudWatch", 1210, 170, "CloudWatch alarms\n5xx · unhealthy hosts · CPU")
    c.icon("architecture-service", "AmazonSimpleNotificationService", 1380, 170, "SNS\nemail / chat", 40)

    c.arrow([(120, 170), (246, 170)], num=1, label="make build", label_at=0.3, label_dy=-30)
    c.arrow([(294, 170), (426, 170)], num=2, label="image tag = git SHA", label_at=0.3, label_dy=-30)
    c.arrow([(204, 300), (640, 300), (640, 246)], num=3, dashed=True,
            label="parameters (pAlbScheme, CIDRs, task sizes, secret ARNs)", label_at=0.5, label_dy=-8)
    c.arrow([(474, 170), (616, 170)], label="image URI", label_at=0.5, label_dy=14)
    c.arrow([(664, 170), (806, 170)], num=4, label="UpdateService", label_at=0.3, label_dy=-30)
    c.arrow([(854, 170), (996, 170)], num=5, label="register new task, drain old", label_at=0.3, label_dy=-30)
    c.arrow([(1044, 170), (1186, 170)], num=6, label="metrics", label_at=0.3, label_dy=-30)
    c.arrow([(1234, 170), (1356, 170)], label="alarm", label_at=0.5, label_dy=-30)
    c.arrow([(830, 146), (830, 110), (660, 110), (660, 146)], dashed=True,
            label="rollback on failed deployment", label_at=0.5, label_dy=-8)
    return c


# --- main ----------------------------------------------------------------------

DIAGRAMS = {
    "architecture": diagram_architecture,
    "request-flow": diagram_request_flow,
    "agent-vpc-mode": diagram_agent_vpc,
    "deploy-pipeline": diagram_pipeline,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--icons", required=True, help="path to aws-icons/icons (contains architecture-service/, resource/, ...)")
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--png", action="store_true", help="also export PNG via rsvg-convert")
    args = ap.parse_args()

    ic = Icons(args.icons)
    os.makedirs(args.out, exist_ok=True)
    for name, fn in DIAGRAMS.items():
        canvas = fn(ic)
        svg_path = os.path.join(args.out, f"{name}.svg")
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(canvas.render())
        print(f"wrote {svg_path}")
        if args.png:
            png_path = os.path.join(args.out, f"{name}.png")
            subprocess.run(["rsvg-convert", "-z", "2", "-o", png_path, svg_path], check=True)
            print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
