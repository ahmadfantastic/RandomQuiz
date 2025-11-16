import { useEffect, useState } from 'react';
import api from '@/lib/api';

let cachedConfig = null;
let cachedError = '';
let pendingRequest = null;

export const useResponseConfig = () => {
  const [config, setConfig] = useState(() => cachedConfig);
  const [error, setError] = useState(() => cachedError);
  const [isLoading, setIsLoading] = useState(() => !cachedConfig && !cachedError);

  useEffect(() => {
    let isMounted = true;
    if (!cachedConfig && !cachedError && !pendingRequest) {
      pendingRequest = api
        .get('/api/response-config/')
        .then((res) => {
          cachedConfig = res.data;
          cachedError = '';
          return cachedConfig;
        })
        .catch((err) => {
          cachedError = 'Unable to load the rating rubric.';
          throw err;
        })
        .finally(() => {
          pendingRequest = null;
        });
    }

    if (pendingRequest) {
      pendingRequest
        .then((data) => {
          if (!isMounted) return;
          setConfig(data);
          setError('');
          setIsLoading(false);
        })
        .catch(() => {
          if (!isMounted) return;
          setError('Unable to load the rating rubric.');
          setIsLoading(false);
        });
    } else {
      setConfig(cachedConfig);
      setError(cachedError);
      setIsLoading(false);
    }

    return () => {
      isMounted = false;
    };
  }, []);

  return { config, error, isLoading };
};
