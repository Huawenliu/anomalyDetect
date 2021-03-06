# -*- coding: utf-8 -*-

from .base import BaseAnomalyDetector

import numpy as np
from .utils import maybe_default_random_state

class IForest(BaseAnomalyDetector):
    """Isolation Forest
    
    Detect anomalies using a forest of space-partitioning trees to measure, on
    average, the ease with which a point can be isolated from a random sample 
    of the data.
    
    Parameters
    ----------
    `num_tree' : int, optional (default=20)
        The number of trees to construct.
    
    `subsample_size' : int or float, optional (default=0.25)
        The size of the random samples of the input data which are used to
        build the trees.
          - If int, then sample `subsample_size' number of data points.
          - If float, then `subsample_size' should be in the range (0, 1) and
            sample ceil(`subsample_size' * m) points where m is the number of
            data points.
     
    `height_limit' : int or None, optional (default=None)
        The maximum height of a tree, equivalent to the maximum number of
        splits. Should be non-negative. 
        If None, the maximum height will be set to np.ceil(np.log2(psi)) where
        psi is the sample size as determined by `subsample_size'.
        
    `random_state' : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.        
        
    References
    ----------

    .. [1] Liu, F.T.; Kai Ming Ting; Zhi-Hua Zhou, "Isolation Forest," Data Mining, 2008.
    
    .. [2] Fei Tony Liu, Kai Ming Ting, and Zhi-Hua Zhou. 2012. Isolation-Based Anomaly Detection. ACM Trans. Knowl. Discov. Data 6, 1, Article 3 (March 2012), 39 pages. DOI=10.1145/2133360.2133363 http://doi.acm.org/10.1145/2133360.2133363 (longer version of [1])

    .. [3] Liu, F.T.; Kai Ming Ting; Zhi-Hua Zhou, "On Detecting Clustered Anomalies Using SCiForest," ECML 2010.

    """
    
    def __init__(self, num_trees=20, subsample_size=0.25, height_limit=None, random_state=None):
        self.num_trees = num_trees
        self.subsample_size = subsample_size
        self.trees = []
        self.height_limit = height_limit
        self.random_state = random_state
        
    def fit(self, X, y=None):
        random_state = maybe_default_random_state(self.random_state)
        
        m = X.shape[0]
        if self.subsample_size <= 1.0:
            psi = int(np.ceil(self.subsample_size * m))
        else:
            psi = self.subsample_size
        if self.height_limit is None:
            self.height_limit = np.ceil(np.log2(psi))
        numdata = X.shape[0]
        trees = []
        for i in range(self.num_trees):
            sample_ind = random_state.permutation(numdata)[:psi]
            X_sample = X[sample_ind, :]
            trees.append(ITree(height_limit=self.height_limit, random_state=random_state).fit(X_sample))
        self.trees = trees
        self.psi = psi
        return self
        
    def predict(self, X):
        m = X.shape[0]
        scores = np.zeros(m)
        for i in range(m):
            x = X[i, :]
            for tree in self.trees:
                path_length, leaf_size = tree.path_length_and_leaf_size(x)
                scores[i] += path_length + _adjustment(leaf_size)
        
        scores = 2**(-scores / len(self.trees) / _adjustment(self.psi))
        return scores
        
def _adjustment(n):
        if n<=1:
            value = 0
        elif n == 2:
            value = 1
        else:
            value = 2 * (np.log(n-1)+0.5772156649) - 2*(n-1) / n;
        return value
    
class ITree(object):
    """ITree
    An ITree is constructed out of ITreeNode's and ITreeLeaf's
    """
    
    def __init__(self, height_limit, root=None, random_state=None):
        self.height_limit = height_limit
        self.root = None
        self.random_state = random_state
        
    def fit(self, X):
        '''
        Given a dataset `X`, construct the ITree out of ITreeNodes and ITreeLeaf's
        '''
        self.root = self._grow(X, 0, self.height_limit)
        return self
    
    def path_length_and_leaf_size(self, x):
        '''
        Return path length of x traversing this ITree and the size of the leaf reached
        '''
        treenode = self.root
        path_length = 0
        while not isinstance(treenode, ITreeLeaf):
            if treenode.compare(x):
                treenode = treenode.get_right()
            else:
                treenode = treenode.get_left()
            path_length += 1
        return (path_length, treenode.size)
          
    def _grow(self, X, current_height, height_limit):
        '''
        Recursive function to grow the forest
        '''
        m, n = X.shape
        if current_height >= height_limit or m <= 1:
            tree = ITreeLeaf(m)
        else:
            split_att = self.random_state.randint(n)
            a = min(X[:, split_att])
            b = max(X[:, split_att])
            split_value = a + (b-a)*self.random_state.random_sample()
            
            X_left = X[X[:, split_att] < split_value]
            X_right = X[X[:, split_att] >= split_value]
            
            tree = ITreeNode(split_att, split_value)
            tree.insert_left(self._grow(X_left, current_height + 1, height_limit))
            tree.insert_right(self._grow(X_right, current_height + 1, height_limit))
        
        return tree

class ITreeNode(object):
    """ITreeNode
    A class to represent an internal (non-leaf) node of an isolation tree
    """
    
    def __init__(self, splitatt, splitvalue):
        self.split_attribute = splitatt
        self.split_value = splitvalue
        self._left = None
        self._right = None
    
    def insert_left(self, new_node):
        self._left = new_node
        
    def insert_right(self, new_node):
        self._right = new_node
     
    def get_right(self):
        return self._right
    def get_left(self):
        return self._left
        
    def compare(self, x):
        """
        Returns a boolean value determining whether we should go left or right
        based on the compare_value
        True - right
        False - left
        """
        
        return x[self.split_attribute] >= self.split_value
    
class ITreeLeaf(object):
    """ITreeLeaf
    A class to represent the leaf (external node) of an isolation tree
    """
    
    def __init__(self, size):
        self.size = size