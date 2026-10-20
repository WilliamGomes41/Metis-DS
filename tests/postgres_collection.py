"""Find database use in selected pytest functions without importing their helpers."""
import ast
import inspect
from pathlib import Path


class PostgresCollectionInputs:
    def __init__(self, root):
        self.tests = Path(root) / 'tests'
        self.modules = {}
        self.results = {}

    def _module(self, path):
        if path not in self.modules:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            functions = {n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
            imports = self._imports(n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
            self.modules[path] = functions,imports
        return self.modules[path]

    def _imports(self, nodes):
        imports = {}
        for parent in nodes:
            for node in ast.walk(parent):
                if isinstance(node, ast.ImportFrom) and node.module == 'tests':
                    for alias in node.names:
                        path = self.tests / (alias.name + '.py')
                        imports[alias.asname or alias.name] = path, None
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('tests.'):
                            path = self.tests.parent.joinpath(*alias.name.split('.')).with_suffix('.py')
                            imports[alias.asname or alias.name] = path, None
                elif isinstance(node,ast.ImportFrom) and (node.module or '').startswith('tests.'):
                    path = self.tests.parent.joinpath(*node.module.split('.')).with_suffix('.py')
                    for alias in node.names:
                        imports[alias.asname or alias.name] = path,alias.name
        return imports

    @staticmethod
    def _direct(node):
        constructors = {'OperationsConsole','DurablePublicationConsole','AzureAuthoritativePublicationConsole',
                        'complete_console','production_console','production_app','production_application',
                        'create_console_app','build_app'}
        for child in ast.walk(node):
            if isinstance(child,ast.Call):
                name = child.func.id if isinstance(child.func,ast.Name) else child.func.attr if isinstance(child.func,ast.Attribute) else ''
                if name in constructors:
                    return True
                if isinstance(child.func,ast.Attribute):
                    owner = ast.unparse(child.func.value)
                    if child.func.attr == 'connect' and owner == 'psycopg':
                        return True
                    if child.func.attr in {'get','getenv'} and owner in {'os','os.environ'}:
                        if child.args and isinstance(child.args[0],ast.Constant) and child.args[0].value == 'METIS_TEST_POSTGRES_DSN':
                            return True
            if isinstance(child,ast.Subscript) and isinstance(child.slice,ast.Constant):
                if ast.unparse(child.value) == 'os.environ' and child.slice.value == 'METIS_TEST_POSTGRES_DSN':
                    return True
        return False

    def _function(self, path, name, visiting):
        key = path,name
        if key in self.results:
            return self.results[key]
        if key in visiting or not path.is_file():
            return False
        functions,imports = self._module(path)
        node = functions.get(name)
        if node is None:
            return False
        if self._direct(node):
            self.results[key] = True
            return True
        visiting = visiting | {key}
        imports = {**imports,**self._imports([node])}
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            target = None
            if isinstance(child.func, ast.Name):
                callee = child.func.id
                target = (path, callee) if callee in functions else imports.get(callee)
            elif isinstance(child.func, ast.Attribute):
                owner = imports.get(ast.unparse(child.func.value))
                if owner and owner[1] is None:
                    target = owner[0], child.func.attr
            if target and self._function(*target,visiting):
                self.results[key] = True
                return True
        self.results[key] = False
        return False

    def function(self, function):
        source = inspect.getsourcefile(function)
        if source is None:
            return False
        path = Path(source)
        if not path.is_relative_to(self.tests):
            return False
        return self._function(path,function.__name__,set())

    def item(self, item):
        if self.function(item.function):
            return True
        for definitions in item._fixtureinfo.name2fixturedefs.values():
            if definitions and self.function(definitions[-1].func):
                return True
        return False
