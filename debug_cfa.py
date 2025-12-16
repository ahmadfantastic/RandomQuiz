import numpy as np
from scipy import optimize
import random

def compute_cfa_one_factor(data_rows, criterion_map_order):
    print(f"Running CFA with {len(data_rows)} rows and {len(criterion_map_order)} vars")
    clean_rows = []
    for row in data_rows:
        if all(c in row and row[c] is not None for c in criterion_map_order):
            clean_rows.append([row[c] for c in criterion_map_order])
            
    n_samples = len(clean_rows)
    p_vars = len(criterion_map_order)
    
    if p_vars < 3 or n_samples < 20: 
        print(f"Failed prereq: p={p_vars}, n={n_samples}")
        return None

    X = np.array(clean_rows)
    
    try:
        S = np.corrcoef(X, rowvar=False)
        print("Correlation Matrix S:\n", S)
    except Exception as e:
        print("Corr calc failed", e)
        return None
        
    if np.any(np.isnan(S)) or np.any(np.isinf(S)):
        print("S has nans or infs")
        return None

    def get_sigma(params):
        lam = params[:p_vars].reshape(-1, 1)
        psi_diag = params[p_vars:]
        psi_diag = np.maximum(psi_diag, 0.001) 
        Sigma = np.dot(lam, lam.T) + np.diag(psi_diag)
        return Sigma

    def objective(params):
        Sigma = get_sigma(params)
        try:
            sign, logdet_sigma = np.linalg.slogdet(Sigma)
            if sign <= 0: return 1e10
            Sigma_inv = np.linalg.inv(Sigma)
            trace_term = np.trace(np.dot(S, Sigma_inv))
            return logdet_sigma + trace_term
        except np.linalg.LinAlgError:
            return 1e10

    initial_guess = np.concatenate([np.full(p_vars, 0.5), np.full(p_vars, 0.5)])
    bounds = [(None, None)] * p_vars + [(0.001, None)] * p_vars
    
    res = optimize.minimize(objective, initial_guess, method='L-BFGS-B', bounds=bounds)
    print("Optimization Result:", res.success, res.message)
    
    if not res.success:
        return None
        
    final_params = res.x
    Sigma_hat = get_sigma(final_params)
    
    sign_s, logdet_s = np.linalg.slogdet(S)
    sign_sigma, logdet_sigma = np.linalg.slogdet(Sigma_hat)
    
    print(f"LogDet S: {logdet_s}, LogDet SigmaHat: {logdet_sigma}")

    if sign_s <= 0 or sign_sigma <= 0:
        print("Logdet failed sign check")
        return None
        
    try:
        Sigma_inv = np.linalg.inv(Sigma_hat)
        trace_term = np.trace(np.dot(S, Sigma_inv))
        f_min = logdet_sigma - logdet_s + trace_term - p_vars
        f_min = max(0, f_min)
        print(f"F_min: {f_min}")
    except Exception as e:
        print("Calc failed", e)
        return None

    chi_square = (n_samples - 1) * f_min
    df = (p_vars * (p_vars + 1) / 2) - (2 * p_vars)
    
    rmsea = 0
    if df > 0:
        rmsea = np.sqrt(max(0, chi_square - df) / ((n_samples - 1) * df))

    f_null = -logdet_s 
    chi_null = (n_samples - 1) * f_null
    df_null = (p_vars * (p_vars + 1) / 2) - p_vars 
    
    cfi = 0.0 # Fix init
    if (chi_null - df_null) > 0:
        cfi = 1 - max(0, chi_square - df) / max(0, chi_null - df_null)
    else:
        cfi = 1.0 # If null model is perfect??
    
    loadings = final_params[:p_vars]
    loadings_list = []
    for idx, c_name in enumerate(criterion_map_order):
        loadings_list.append({
            'criterion': c_name,
            'loading': round(float(loadings[idx]), 3)
        })
        
    return {
        'n_samples': n_samples,
        'fit_indices': {
            'chi_square': round(chi_square, 2),
            'df': int(df),
            'rmsea': round(rmsea, 3),
            'cfi': round(cfi, 3)
        },
        'loadings': loadings_list
    }

# Mock Data
rows = []
for i in range(25):
    # Random ints 1-5
    r1 = float(random.randint(1, 5))
    r2 = float(random.randint(1, 5))
    r3 = float(random.randint(1, 5))
    rows.append({'C1': r1, 'C2': r2, 'C3': r3})

res = compute_cfa_one_factor(rows, ['C1', 'C2', 'C3'])
print("Result:", res)
