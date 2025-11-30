"""Test fixture for control_flow and protocol extractors."""

for i in range(10):
    pass

for _key, value in enumerate(["a", "b", "c"]):
    pass

for x, _y in zip([1, 2], [3, 4]):  # noqa: B905 - test fixture
    pass

for _key, value in {"a": 1, "b": 2}.items():
    pass


while True:
    break

count = 0
while count < 10:
    count += 1


async def async_iterate():
    async for _item in async_generator():
        pass


if x > 0:
    pass

if x > 0 or x < 0:
    pass
else:
    pass


match value:
    case 1:
        pass
    case 2 if condition:
        pass
    case _:
        pass


for i in range(10):
    if i == 5:
        break
    if i % 2 == 0:
        continue
    pass


assert x > 0
assert x > 0, "x must be positive"


del x
del mylist[0]
del obj.attr


with open("file.txt") as f:
    pass

async with lock:
    pass

with open("a") as f, open("b") as g:
    pass


class MyIterator:
    def __iter__(self):
        return self

    def __next__(self):
        if condition:
            raise StopIteration
        return value


class MyContainer:
    def __len__(self):
        return 10

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value

    def __delitem__(self, index):
        del self.data[index]

    def __contains__(self, item):
        return item in self.data


class MyCallable:
    def __call__(self, x, y, *args, **kwargs):
        return x + y


from functools import total_ordering


@total_ordering
class MyComparable:
    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        return self.value < other.value


class MyNumber:
    def __add__(self, other):
        return MyNumber(self.value + other.value)

    def __radd__(self, other):
        return MyNumber(other + self.value)

    def __iadd__(self, other):
        self.value += other.value
        return self

    def __mul__(self, other):
        return MyNumber(self.value * other.value)


class MyPickleable:
    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __reduce__(self):
        return (self.__class__, (self.value,))


import weakref

weak_ref = weakref.ref(obj)
weak_proxy = weakref.proxy(obj)
weak_dict = weakref.WeakValueDictionary()


from contextvars import ContextVar

my_var = ContextVar("my_var")
token = my_var.set("value")
value = my_var.get()


if __name__ == "__main__":
    print(__file__)
    print(__doc__)

__all__ = ["MyIterator", "MyContainer"]


@dataclass
class MyData:
    x: int
    y: str


@total_ordering
class MyOrdered:
    pass


@custom_decorator(arg=value)
class MyCustom:
    pass
