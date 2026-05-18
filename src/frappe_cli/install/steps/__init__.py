from .app import AppGetStep, AppInstallStep
from .bench import BenchInstallStep
from .init_bench import BenchInitStep
from .mariadb import MariaDBInstallStep, MariaDBSecureStep
from .nodejs import NodeJSStep
from .production import ProductionSetupStep
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
    AppInstallStep(),
    ProductionSetupStep(),
    SSLSetupStep(),
]
