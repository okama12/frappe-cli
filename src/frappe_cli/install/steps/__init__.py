from .system import SystemUpdateStep, SystemDepsStep
from .uv_check import UvCheckStep
from .nodejs import NodeJSStep
from .mariadb import MariaDBInstallStep, MariaDBSecureStep
from .redis import RedisStep
from .wkhtmltopdf import WkhtmltopdfStep
from .bench import BenchInstallStep
from .init_bench import BenchInitStep
from .site import SiteCreateStep
from .app import AppGetStep, AppInstallStep
from .production import ProductionSetupStep
from .ssl import SSLSetupStep

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
    AppInstallStep(),
    ProductionSetupStep(),
    SSLSetupStep(),
]
