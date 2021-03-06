"""Module for sedes objects that use lists as serialization format."""


from collections import Sequence
from functools import partial
from itertools import izip, imap
from ..exceptions import SerializationError, DeserializationError


def is_sedes(obj):
    """Check if `obj` is a sedes object.
    
    A sedes object is characterized by having the methods `serialize(obj)` and
    `deserialize(serial)`.
    """
    methods = ('serialize', 'deserialize')
    return all(hasattr(obj, m) for m in ('serialize', 'deserialize'))


def is_sequence(obj):
    """Check if `obj` is a sequence, but not a string."""
    return isinstance(obj, Sequence) and not isinstance(obj, basestring)


class List(list):
    """A sedes for lists, implemented as a list of other sedes objects."""

    def __init__(self, elements=[]):
        super(List, self).__init__()
        for e in elements:
            if is_sedes(e):
                self.append(e)
            elif isinstance(e, Sequence):
                self.append(List(e))
            else:
                raise TypeError('Instances of List must only contain sedes '
                                'objects or nested sequences thereof.')

    def serialize(self, obj):
        if not is_sequence(obj):
            raise SerializationError('Can only serialize sequences', obj)
        if len(self) != len(obj):
            raise SerializationError('List has wrong length', obj)
        return [sedes.serialize(element)
                for element, sedes in izip(obj, self)]

    def deserialize(self, serial):
        if not is_sequence(serial):
            raise DeserializationError('Can only deserialize sequences',
                                       serial)
        if len(serial) != len(self):
            raise DeserializationError('List has wrong length', serial)
        return [sedes.deserialize(element) 
                for element, sedes in izip(serial, self)]


class CountableList(object):
    """A sedes for lists of arbitrary length.

    :param element_sedes: when (de-)serializing a list, this sedes will be
                          applied to all of its elements
    """

    def __init__(self, element_sedes):
        self.element_sedes = element_sedes

    def serialize(self, obj):
        if not is_sequence(obj):
            raise SerializationError('Can only serialize sequences', obj)
        return [self.element_sedes.serialize(e) for e in obj]

    def deserialize(self, serial):
        if not is_sequence(serial):
            raise DeserializationError('Can only deserialize sequences', serial)
        return [self.element_sedes.deserialize(e) for e in serial]


class Serializable(object):
    """Base class for objects which can be serialized into RLP lists.

    :attr:`fields` defines which attributes are serialized and how this is
    done. It is expected to be an ordered sequence of 2-tuples
    ``(name, sedes)``. Here, ``name`` is the name of an attribute and ``sedes``
    is the sedes object that will be used to serialize the corresponding
    attribute. The object as a whole is then serialized as a list of those
    fields.

    :cvar fields: a list of 2-tuples ``(name, sedes)`` where ``name`` is a
                  string corresponding to an attribute and ``sedes`` is the
                  sedes object used for (de)serializing the attribute.
    :param \*args: initial values for the first attributes defined via
                  :attr:`fields`
    :param \*\*kwargs: initial values for all attributes not initialized via
                       positional arguments
    """

    fields = tuple()
    _sedes = None

    def __init__(self, *args, **kwargs):
        # check keyword arguments are known
        field_set = set(field for field, _ in self.fields)

        # set positional arguments
        for (field, _), arg in izip(self.fields, args):
            setattr(self, field, arg)
            field_set.remove(field)

        # set keyword arguments, if not already set
        for (field, value) in kwargs.iteritems():
            if field in field_set:
                setattr(self, field, value)
                field_set.remove(field)

        if len(field_set) != 0:
            raise TypeError('Not all fields initialized')

    def __eq__(self, other):
        """Two objects are equal, if they are equal after serialization."""
        if not hasattr(other.__class__, 'serialize'):
            return False
        return self.serialize(self) == other.serialize(other)

    def __ne__(self, other):
        return not self == other

    @classmethod
    def get_sedes(cls):
        if not cls._sedes:
            cls._sedes = List(sedes for _, sedes in cls.fields)
        return cls._sedes

    @classmethod
    def serialize(cls, obj):
        if not hasattr(obj, 'fields'):
            raise SerializationError('Cannot serialize this object', obj)
        try:
            field_values = [getattr(obj, field) for field, _ in cls.fields]
        except AttributeError:
            raise SerializationError('Cannot serialize this object', obj)
        return cls.get_sedes().serialize(field_values)

    @classmethod
    def deserialize(cls, serial, **kwargs):
        values = cls.get_sedes().deserialize(serial)
        params = {field: value for (field, _), value
                               in izip(cls.fields, values)}
        return cls(**dict(params.items() + kwargs.items()))

    @classmethod
    def exclude(cls, excluded_fields):
        """Create a new sedes considering only a reduced set of fields."""
        class SerializableExcluded(cls):
            fields = [(field, sedes) for field, sedes in cls.fields
                                     if field not in excluded_fields]
            _sedes = None
        return SerializableExcluded
