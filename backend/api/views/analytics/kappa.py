
import numpy as np
import logging

logger = logging.getLogger(__name__)


def quadratic_weighted_kappa(rater_a, rater_b, min_rating=None, max_rating=None, possible_ratings=None, context=None):
    """
    Calculates the quadratic weighted kappa (Cohen's Kappa) between two raters.
    Supports float ratings if possible_ratings is provided or inferred.
    
    Args:
        rater_a (list or np.array): Ratings from the first rater.
        rater_b (list or np.array): Ratings from the second rater.
        min_rating (int/float, optional): Ignored if possible_ratings is derived from data.
        max_rating (int/float, optional): Ignored if possible_ratings is derived from data.
        possible_ratings (list, optional): List of all valid rating values (e.g. [0, 0.5, 1.0]). 
                                           If None, derived from unique values in rater_a and rater_b.
        
    Returns:
        float: The quadratic weighted kappa score. 1.0 is perfect agreement.
    """
    rater_a = np.array(rater_a)
    rater_b = np.array(rater_b)
    
    assert len(rater_a) == len(rater_b), "Rater arrays must be the same length."
    
    if possible_ratings is None:
        # Infer possible ratings from data
        possible_ratings = sorted(list(set(np.concatenate((rater_a, rater_b)))))
    else:
        # Ensure it's sorted and unique
        possible_ratings = sorted(list(set(possible_ratings)))
        # Extend with observed values if any missing (robustness)
        observed = set(np.concatenate((rater_a, rater_b)))
        if not observed.issubset(set(possible_ratings)):
             possible_ratings = sorted(list(set(possible_ratings).union(observed)))

    if len(possible_ratings) <= 1:
        return 1.0
        
    # Map values to indices
    val_to_idx = {val: i for i, val in enumerate(possible_ratings)}
    
    conf_mat = confusion_matrix(rater_a, rater_b, val_to_idx)
    
    # Logging removed


    num_ratings = len(possible_ratings)
    num_scored_items = float(len(rater_a))
    
    if num_scored_items == 0:
        return 0.0

    hist_rater_a = np.sum(conf_mat, axis=1) # Row sums
    hist_rater_b = np.sum(conf_mat, axis=0) # Col sums
    
    numerator = 0.0
    denominator = 0.0
    
    # Calculate weights based on actual value distances
    # w_ij = (rating_i - rating_j)^2 / (max_rating - min_rating)^2
    min_v = possible_ratings[0]
    max_v = possible_ratings[-1]
    max_dist_sq = pow(max_v - min_v, 2.0)
    
    if max_dist_sq == 0:
        return 1.0

    for i in range(num_ratings):
        for j in range(num_ratings):
            expected_count = (hist_rater_a[i] * hist_rater_b[j]) / num_scored_items
            
            val_i = possible_ratings[i]
            val_j = possible_ratings[j]
            
            d = pow(val_i - val_j, 2.0) / max_dist_sq
            
            numerator += d * conf_mat[i][j]
            denominator += d * expected_count
            
    if denominator == 0:
        return 1.0 
    
    return 1.0 - numerator / denominator

def confusion_matrix(rater_a, rater_b, val_to_idx):
    """
    Computes the confusion matrix using value-to-index mapping.
    """
    num_ratings = len(val_to_idx)
    matrix = np.zeros((num_ratings, num_ratings), dtype=int)
    
    for a, b in zip(rater_a, rater_b):
        idx_a = val_to_idx[a]
        idx_b = val_to_idx[b]
        matrix[idx_a][idx_b] += 1
        
    return matrix
