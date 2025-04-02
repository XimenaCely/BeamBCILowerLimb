from typing import List, Union, Callable


class Parameter:
    DEFAULT = None
    TYPES = Union[str, float, int, list, bool, Callable]

    def __init__(
        self,
        name: str,
        displayname: str,
        data_type: type,
        default_value: TYPES,
        unit: Union[str, List[str]],
        description: str = "",
        value=DEFAULT,
    ):
        self.name = name
        self.displayname = displayname
        self.data_type = data_type
        self.default_value = default_value
        self.unit = unit
        self.description = description

        self.setValue(value)

    def getValue(self) -> TYPES:
        return self.value

    def setValue(self, val: TYPES) -> bool:
        if val == Parameter.DEFAULT:
            self.value = self.default_value
        if type(val) == self.data_type:
            self.value = val
            return True
        if self.data_type is list and val in self.unit:
            self.value = val
            return True
        return False

    def __str__(self):
        return "Parameter(name: '{}', type: {}, value: '{}', unit: '{}' default: '{}', description: '{}')".format(
            self.name,
            self.data_type,
            self.value,
            self.unit,
            self.default_value,
            self.description,
        )

    def __repr__(self):
        return self.__str__()
