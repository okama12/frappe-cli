from .app import AppGetStep, AppInstallStep
from .bench import BenchInstallStep
from .dns_multitenant import DnsMultitenantStep
from .init_bench import BenchInitStep
from .mariadb import MariaDBInstallStep, MariaDBSecureStep
from .nodejs import NodeJSStep
from .production import BenchRestartStep, ProductionSetupStep
from .redis import RedisStep
from .site import SiteCreateStep
from .ssl import SSLSetupStep
from .system import SystemDepsStep, SystemUpdateStep
from .uv_check import UvCheckStep
from .wkhtmltopdf import WkhtmltopdfStep

ALL_STEPS = [
    SystemUpdateStep(),
    SystemDepsStep(),
    UvCheckStep(),
    NodeJSStep(),
    MariaDBInstallStep(),
    MariaDBSecureStep(),
    RedisStep(),
    WkhtmltopdfStep(),
    BenchInstallStep(),
    BenchInitStep(),
    SiteCreateStep(),
    AppGetStep(),
    # Enable hostname-based routing before nginx config is generated so the
    # site is reachable by FQDN. Mirrors the manual runbook (Step 4.1).
    DnsMultitenantStep(),
    # Production setup runs before app install so that supervisor starts
    # bench's Redis (queue/cache/socketio). bench install-app requires it.
    # ProductionSetupStep self-heals the supervisor symlink and hard-verifies
    # both supervisor RUNNING and Redis PONG before returning.
    ProductionSetupStep(),
    AppInstallStep(),
    BenchRestartStep(),
    SSLSetupStep(),
]
