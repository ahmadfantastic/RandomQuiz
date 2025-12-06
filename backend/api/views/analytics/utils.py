import numpy as np

def calculate_weighted_kappa(y1, y2, all_categories=None, label=None):
    # y1, y2 are lists of ratings
    # Assume scale is ordinal integers
    # all_categories: Optional list of all possible scale values to ensure matrix shape
    # label: Optional string description for logging

    
    # Ensure inputs are numpy arrays
    y1 = np.array(y1)
    y2 = np.array(y2)
    
    # Get unique categories
    if all_categories is not None:
        categories = np.array(all_categories)
        categories.sort()
    else:
        categories = np.unique(np.concatenate((y1, y2)))
        categories.sort()

    
    # Map categories to 0..k-1
    cat_map = {c: i for i, c in enumerate(categories)}
    y1_idx = np.array([cat_map[c] for c in y1])
    y2_idx = np.array([cat_map[c] for c in y2])
    
    k = len(categories)
    n = len(y1)
    
    if k < 2:
        return 1.0 # Perfect agreement if only 1 category
        
    # Confusion matrix
    conf_mat = np.zeros((k, k))
    for i in range(n):
        conf_mat[y1_idx[i], y2_idx[i]] += 1
        
    # Weights matrix (quadratic)
    w_mat = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            w_mat[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)
            
    # Expected matrix
    row_sums = np.sum(conf_mat, axis=1)
    col_sums = np.sum(conf_mat, axis=0)
    expected_mat = np.outer(row_sums, col_sums) / n
    
    # Calculate Kappa
    numerator = np.sum(w_mat * conf_mat)
    denominator = np.sum(w_mat * expected_mat)
    
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
        
    return 1.0 - (numerator / denominator)
