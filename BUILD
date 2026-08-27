rules = load("//infra/rules.py")
variables = load("//src/variables.py")
check_types = load("//infra/check_types.py")

def impl(ctx):
    ctx.sh("python -m venv env", env=variables.ENV)
    ctx.sh("env/bin/pip install -r requirements.txt", env=variables.ENV)
    ctx.sh("yarn", env=variables.ENV)
    ctx.sh("env/bin/python ./manage.py build", env=variables.ENV)

rules.declare_app(
    name="oh",
    srcs=find("**/*", unsafe_ignore_extension=True),
    deps=[":common"],
    impl=impl,
    checks=[
        check_types.yarn("oh_queue/static/js", prettier=True),
    ],
)
