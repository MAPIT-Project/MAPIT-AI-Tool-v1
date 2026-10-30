import { getAuth } from 'firebase/auth';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token cache to avoid repeated token fetches
let tokenCache: { token: string; timestamp: number; email: string } | null = null;
const TOKEN_CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export const apiCall = async (
  endpoint: string,
  options: RequestInit = {},
  timeoutMs: number = 30000 // 30 second default timeout
): Promise<Response> => {
  const auth = getAuth();
  const user = auth.currentUser;
  
  console.log('apiCall: endpoint=', endpoint, 'user=', user ? 'exists' : 'null');
  
  if (!user) {
    console.log('apiCall: User not authenticated, throwing error');
    throw new Error('User not authenticated');
  }

  try {
    const userEmail = user.email || 'unknown@example.com';
    
    // Check if we have a valid cached token
    const now = Date.now();
    if (tokenCache && 
        tokenCache.email === userEmail && 
        (now - tokenCache.timestamp) < TOKEN_CACHE_DURATION) {
      console.log('apiCall: Using cached token');
    } else {
      // Fetch new token and cache it
      console.log('apiCall: Fetching new token');
      const token = await user.getIdToken();
      tokenCache = {
        token,
        timestamp: now,
        email: userEmail
      };
    }
    
    const token = tokenCache!.token;
    console.log('apiCall: Got token, length=', token.length, 'making request to', `${API_BASE_URL}${endpoint}`);
    
    const enhancedToken = token;
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${enhancedToken}`,
    };

    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    // Create a timeout promise
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(`Request timeout after ${timeoutMs}ms`)), timeoutMs);
    });

    // Race between the fetch and timeout
    const response = await Promise.race([
      fetch(`${API_BASE_URL}${endpoint}`, config),
      timeoutPromise
    ]);
    
    console.log('apiCall: Response status:', response.status);
    return response;
  } catch (error) {
    console.error('apiCall: Error getting token or making request:', error);
    throw error;
  }
};

export const apiStream = async (
  endpoint: string,
  data: any,
  onChunk: (chunk: any) => void,
  onEnd: (metadata?: any) => void,
  onError: (error: any) => void
): Promise<void> => {
  const auth = getAuth();
  const user = auth.currentUser;
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  try {
    const token = await user.getIdToken();
    const enhancedToken = token;
    
    console.log('apiStream: Making request to', `${API_BASE_URL}${endpoint}`)
    console.log('apiStream: Request data:', data)
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${enhancedToken}`,
      },
      body: JSON.stringify(data),
    });

    console.log('apiStream: Response status:', response.status)
    console.log('apiStream: Response headers:', response.headers)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('apiStream: HTTP error response:', errorText)
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let chunkCount = 0

    console.log('apiStream: Starting to read stream...')

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log('apiStream: Stream reading completed')
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '') continue // Skip empty lines
        
        if (line.startsWith('data: ')) {
          try {
            const jsonData = JSON.parse(line.slice(6));
            chunkCount++
            console.log(`apiStream: Received chunk ${chunkCount}:`, jsonData)
            onChunk(jsonData);
            
            if (jsonData.type === 'end') {
              console.log('apiStream: Received end signal with metadata:', jsonData.metadata)
              onEnd(jsonData.metadata);
              return;
            }
          } catch (e) {
            console.error('apiStream: Error parsing streaming data:', e, 'Line:', line);
          }
        } else {
          console.log('apiStream: Non-data line received:', line)
        }
      }
    }
    
    console.log('apiStream: Stream processing completed')
  } catch (error) {
    console.error('apiStream: Error in streaming request:', error);
    onError(error);
  }
};

export const apiGet = (endpoint: string, timeoutMs?: number) => apiCall(endpoint, { method: 'GET' }, timeoutMs);
export const apiPost = (endpoint: string, data?: any) => 
  apiCall(endpoint, { 
    method: 'POST', 
    body: data ? JSON.stringify(data) : undefined 
  });
export const apiPut = (endpoint: string, data?: any) => 
  apiCall(endpoint, { 
    method: 'PUT', 
    body: data ? JSON.stringify(data) : undefined 
  });
export const apiDelete = (endpoint: string) => 
  apiCall(endpoint, { method: 'DELETE' });

// Function to clear token cache (call on logout)
export const clearTokenCache = () => {
  tokenCache = null;
  console.log('Token cache cleared');
};

// Co-participation visualization API functions
export async function postExpand(text: string) {
  const res = await apiPost("/ai/expand", { text });
  if (!res.ok) throw new Error("Expand failed");
  return res.json() as Promise<{expanded_query: string; expanded_query_lucene: string;}>;
}

export type VisualizePayload = {
  expanded_query_lucene: string;
  min_score?: number;
  min_weight?: number;
  epsilon?: number;
  limit?: number;
  run_louvain?: boolean;
  graph_name?: string;
  write_prop?: string;
};

export async function postVisualize(payload: VisualizePayload) {
  const res = await apiPost("/org/visualize", payload);
  if (!res.ok) throw new Error("Visualize failed");
  return res.json() as Promise<{ ok: boolean; url: string }>;
}

export async function postFindPartners(query: string) {
  const res = await apiPost("/org/find-partners", { query });
  if (!res.ok) throw new Error("Partner search failed");
  return res.json() as Promise<{ ok: boolean; partners: any[]; original_query: string; expanded_query: string }>;
}

export async function postFindPartnersWithLucene(luceneQuery: string) {
  const res = await apiPost("/org/find-partners-with-lucene", { lucene_query: luceneQuery });
  if (!res.ok) throw new Error("Partner search failed");
  return res.json() as Promise<{ ok: boolean; partners: any[]; lucene_query: string }>;
}

export async function postCoParticipationWithLucene(luceneQuery: string) {
  const res = await apiPost("/org/co-participation-with-lucene", { lucene_query: luceneQuery });
  if (!res.ok) throw new Error("Co-participation visualization failed");
  return res.json() as Promise<{ ok: boolean; url: string; lucene_query: string }>;
}

export async function postHeatmapWithLucene(luceneQuery: string, metric: string = "projects") {
  const res = await apiPost("/org/heatmap", { 
    lucene_query: luceneQuery,
    metric: metric
  });
  if (!res.ok) throw new Error("Heatmap data fetch failed");
  return res.json() as Promise<{ 
    ok: boolean; 
    data: Array<{country: string; projects: number; ec_sum: number}>; 
    lucene_query: string; 
    metric: string 
  }>;
}

export type DataSummaryCounts = {
  projects: number;
  deliverables: number;
  partners: number;
  publications: number;
  authors: number;
};

export async function getDataSummary() {
  const res = await apiGet('/org/data-summary', 30000);
  if (!res.ok) throw new Error('Data summary fetch failed');
  return res.json() as Promise<{ ok: boolean; counts: DataSummaryCounts }>;
}