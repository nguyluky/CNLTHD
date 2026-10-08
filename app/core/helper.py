from collections import deque
import inspect
import re
from typing import Generator


def camel_to_upper_snake_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).upper()


def get_all_subclasses(cls: type) -> Generator[type, None, None]:
    seen = set()
    # Use a queue to traverse the inheritance tree
    queue = deque(cls.__subclasses__())

    while queue:
        subclass = queue.popleft()
        if subclass not in seen:
            seen.add(subclass)
            if not subclass.__name__.startswith("_"):  # Ignore private classes
                yield subclass
            # Add this subclass's children to the queue
            queue.extend(subclass.__subclasses__())

def print_tree(cls: type, prefix="", is_last=True, show_doc=True):
    connector = "└── " if is_last else "├── "

    doc = inspect.getdoc(cls)
    description = doc.splitlines()[0].strip() if doc and show_doc else ""

    print(f"{prefix}{connector}{cls.__name__} - {description}")

    subclasses = [
        sub for sub in cls.__subclasses__()
        if not sub.__name__.startswith("_")
    ]

    new_prefix = prefix + ("    " if is_last else "│   ")

    for index, subclass in enumerate(subclasses):
        print_tree(
            subclass,
            new_prefix,
            index == len(subclasses) - 1,
            show_doc,
        )



if __name__ == "__main__":
    from sqlalchemy.exc import SQLAlchemyError
    
    print("Tree of subclasses for SQLAlchemyError:")
    print_tree(SQLAlchemyError)