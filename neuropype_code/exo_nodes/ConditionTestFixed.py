import numpy as np

from ...engine import *


class ConditionTestFixed(Node):
    """Basic conditional test node."""

    # --- Input/output ports ---
    input = DataPort(object, "Input condition.", IN, setifequal=False)
    true = DataPort(bool, "True branch. Executed if condition is true.", OUT)
    false = DataPort(
        bool, "False branch. Executed if condition is false.", OUT)

    # --- Properties ---
    value = Port(None, object, """The value to compare to. Usually a scalar.
        """, verbose_name='comparison value')
    operator = EnumPort("equal", ["equal", "not_equal", "greater", "less",
                                  "greater_equal", "less_equal"], """Comparison 
        operator to use. Tests whether the input is greater/less/etc than the 
        given value.""", verbose_name='comparison operator')
    collapse_op = EnumPort("all", ["any", "all"], """Collapse operation. This is 
        optional and only used if the input is an array.
        """, verbose_name='collapse operation', expert=True)

    def __init__(self, value: Union[object, None, Type[Keep]] = Keep, operator: Union[str, None, Type[Keep]] = Keep, collapse_op: Union[str, None, Type[Keep]] = Keep, **kwargs):
        """Create a new node. Accepts initial values for the ports."""
        super().__init__(value=value, operator=operator, collapse_op=collapse_op, **kwargs)

    @classmethod
    def description(cls):
        """Declare descriptive information about the node."""
        return Description(name='Condition Test',
                           description="""Basic condition test node. The node
                           has one input of arbitrary type and two outputs that
                           can take on values 0 or 1, named true and false.
                           Further, the node has a predefined value to compare 
                           to, and optionally the type of comparison can be 
                           specified. If the comparison between the value and
                           the input yields True, then the output named "true"
                           outputs 1, and otherwise the output named "false"
                           yields 1. These outputs can be wired to the "update"
                           port of subsequent nodes to control whether these
                           nodes shall execute (i.e., be updated) or not.""",
                           version='1.0.0', status=DevStatus.beta)

    @input.setter
    def input(self, v):
        # elementwise compare
        if v is not None:
            v = np.array(v).astype(object)

        if self.operator == "equal":
            res = np.equal(v, self.value)
        elif self.operator == "not_equal":
            res = np.not_equal(v, self.value)
        elif self.operator == "greater":
            res = np.greater(v, self.value)
        elif self.operator == "greater_equal":
            res = np.greater_equal(v, self.value)
        elif self.operator == "less":
            res = np.less(v, self.value)
        elif self.operator == "less_equal":
            res = np.less_equal(v, self.value)
        else:
            raise ValueError("Unsupported operator: %s" % self.operator)
        # collapse
        if self.collapse_op == "all":
            res = np.all(res)
        elif self.collapse_op == "any":
            res = np.any(res)
        else:
            raise ValueError("Unsupported collapse op: %s" % self.collapse_op)
        self._true = res == True
        self._false = res != True
