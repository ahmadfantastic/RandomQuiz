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

def calculate_average_nearest(values, scale_values):
    """
    Aggregates ratings by taking the mean and mapping to the nearest valid scale value.
    """
    from statistics import mean
    if not values:
        return None
    
    avg = mean(values)
    
    # Find scale value with minimum absolute difference from average
    nearest = min(scale_values, key=lambda x: abs(x - avg))
    return nearest

def calculate_typing_metrics(typing_events, attempt_started_at):
    """
    Calculate interaction metrics from a list of typing events.
    typing_events: List of objects/dicts with 'created_at' and 'metadata'.
    attempt_started_at: datetime
    """
    ipl = 0
    revision_ratio = 0
    burstiness = 0
    wpm = 0
    active_time = 0
    final_word_count = 0
    
    if not typing_events:
        return ipl, revision_ratio, burstiness, wpm, active_time, final_word_count

    # Helper to get attr or item
    def get_val(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key)

    first_typing = typing_events[0]
    first_time = get_val(first_typing, 'created_at')
    
    # A. Initial Planning Latency
    if attempt_started_at:
        ipl = (first_time - attempt_started_at).total_seconds()
        ipl = max(0, ipl)
    
    # B. Revision Ratio & Word Count
    total_removed = 0
    total_added = 0
    
    for event in typing_events:
        meta = get_val(event, 'metadata') or {}
        diff = meta.get('diff')
        if diff:
            removed = diff.get('removed', '')
            added = diff.get('added', '')
            total_removed += len(removed)
            total_added += len(added)
        
        if 'text_length' in meta:
            final_word_count = meta['text_length'] / 5.0
            
    if total_added > 0:
        revision_ratio = total_removed / total_added

    # C. Burstiness
    for j in range(1, len(typing_events)):
        curr = get_val(typing_events[j], 'created_at')
        prev = get_val(typing_events[j-1], 'created_at')
        gap = (curr - prev).total_seconds()
        if gap > 10:
            burstiness += 1

    # D. WPM
    last_typing = typing_events[-1]
    last_time = get_val(last_typing, 'created_at')
    active_writing_seconds = (last_time - first_time).total_seconds()
    
    if active_writing_seconds > 0:
        active_time = active_writing_seconds / 60.0
        wpm = final_word_count / active_time

    return ipl, revision_ratio, burstiness, wpm, active_time, final_word_count
