import copy
        
class Node(object):
    _instances = []
    
    def __new__(cls, *args, **kw):
        self = super(Node, cls).__new__(cls)
        Node._instances.append(self)
        return self
        
    def __init__(self, parent, name, attributes=None):
        self.parent = parent
        self.attributes = attributes or {}
        self.data = name
        self.state = "closed"
        self.children = []
    
    def __repr__(self):
        return "Node instance %s at %s" % (self.data, self.position)
        
    def name(self):
        return self.data
        
    def _position(self):
        if self.parent == None:
            return self.data
        return self.parent.position+'.'+self.data
    position = property(_position, None, None)
    
    def appendNode(self, name, attributes=None):
        if not isinstance(name, basestring):
            raise ValueError("'name' should be a string, not %s" % type(name))
        attributes = attributes or {}
        n = Node(self, name, attributes=attributes)
        self.children.append(n)
        return n
    
    @classmethod
    def findNode(cls, position):
        for node in cls._instances:
            if node.position == position:
                return node

if __name__ == '__main__':
    import unittest

    class TestNodes(unittest.TestCase):

        def setUp(self):
            self.n1 = Node(None, data='com')
            self.n2 = Node(self.n1, data='example')
            self.n3 = Node(self.n1, data='foobar')
            
        def test_nodes(self):
            self.assertEqual(self.n1.data, self.n1.position)
            self.assertEqual(self.n2.attributes, {})

        def test_append(self):
            self.n3.appendNode("example")
            self.n3.appendNode("com", attributes={'one':1})
            self.assertRaises(ValueError, Node.appendNode, self.n1, self.n1)

        def test_find(self):
            self.assertEqual(Node.findNode("com.foobar").position,
                             self.n3.position)


    unittest.main()
