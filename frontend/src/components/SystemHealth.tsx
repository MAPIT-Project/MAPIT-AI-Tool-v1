import React, { useEffect, useState } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Icon,
  Tooltip,
  Switch,
  Spinner,
} from '@chakra-ui/react';
import { FiRefreshCw, FiDatabase, FiServer, FiCpu, FiGlobe } from 'react-icons/fi';
import { apiGet, apiPost } from '../utils/api';
import { useAuth } from '../contexts/AuthContext';
import { useThemeColors } from '../hooks/useThemeColors';


interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  message: string;
  context_status: 'ready' | 'error' | 'no_results' | 'not_implemented';
}

interface SystemHealthData {
  timestamp: string;
  components: {
    neo4j: HealthStatus;
    qdrant: HealthStatus;
    elasticsearch: HealthStatus;
    postgres: HealthStatus;
    openai: HealthStatus;
  };
}

interface UserPreferences {
  neo4j_enabled: boolean;
  qdrant_enabled: boolean;
  elasticsearch_enabled: boolean;
}

const SystemHealth: React.FC = () => {
  console.log('SystemHealth: Component is rendering');
  const colors = useThemeColors();
  const { currentUser, loading: authLoading } = useAuth();
  const [healthData, setHealthData] = useState<SystemHealthData | null>(null);
  const [userPreferences, setUserPreferences] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingPreferences, setUpdatingPreferences] = useState<string | null>(null);

  const fetchHealthStatus = async () => {
    console.log('SystemHealth: fetchHealthStatus called', { currentUser: !!currentUser, authLoading });
    try {
      setLoading(true);
      const response = await apiGet('/health_system');
      const data = await response.json();
      console.log('SystemHealth: Raw response:', response);
      console.log('SystemHealth: Response data:', data);
      console.log('SystemHealth: Components available:', Object.keys(data.components || {}));
      console.log('SystemHealth: Postgres component:', data.components?.postgres);
      setHealthData(data);
      setError(null);
    } catch (err) {
      console.log('SystemHealth: Error fetching health status', err);
      setError('Failed to fetch health status');
      console.error('Health check error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserPreferences = async () => {
    try {
      const response = await apiGet('/user/preferences');
      const data = await response.json();
      console.log('SystemHealth: User preferences:', data);
      setUserPreferences(data);
    } catch (err) {
      console.log('SystemHealth: Error fetching user preferences', err);
      // Don't set error for preferences, just use defaults
    }
  };

  const updateUserPreference = async (source: string, enabled: boolean) => {
    if (!userPreferences) return;
    
    setUpdatingPreferences(source);
    try {
      const updatedPreferences = {
        ...userPreferences,
        [`${source}_enabled`]: enabled
      };
      
      const response = await apiPost('/user/preferences', updatedPreferences);
      const data = await response.json();
      console.log('SystemHealth: Updated preferences:', data);
      setUserPreferences(data);
    } catch (err) {
      console.log('SystemHealth: Error updating user preferences', err);
      // Revert the change on error
      setUserPreferences(userPreferences);
    } finally {
      setUpdatingPreferences(null);
    }
  };

  useEffect(() => {
    console.log('SystemHealth: useEffect called', { currentUser: !!currentUser, authLoading });
    if (currentUser && !authLoading) {
      console.log('SystemHealth: Starting health polling');
      fetchHealthStatus();
      fetchUserPreferences();
      const interval = setInterval(fetchHealthStatus, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [currentUser, authLoading]);



  const getContextStatusTooltip = (status: string) => {
    switch (status) {
      case 'ready':
        return 'Ready and contributing to responses';
      case 'error':
        return 'Error occurred while getting context';
      case 'no_results':
        return 'No relevant results found';
      case 'not_implemented':
        return 'Context feature not implemented yet';
      default:
        return 'Unknown status';
    }
  };

  const getComponentIcon = (component: string) => {
    switch (component) {
      case 'neo4j':
        return FiDatabase;
      case 'qdrant':
        return FiServer;
      case 'elasticsearch':
        return FiGlobe;
      case 'postgres':
        return FiDatabase;
      case 'openai':
        return FiCpu;
      default:
        return FiServer;
    }
  };

  const getComponentLabel = (component: string) => {
    switch (component) {
      case 'neo4j':
        return 'Graph DB';
      case 'qdrant':
        return 'Vector DB';
      case 'elasticsearch':
        return 'ES/BM25';
      case 'postgres':
        return 'PostgreSQL DB';
      case 'openai':
        return 'OpenAI API';
      default:
        return component;
    }
  };

  const isDataSourceComponent = (component: string) => {
    return ['neo4j', 'qdrant', 'elasticsearch'].includes(component);
  };

  const getDataSourceEnabled = (component: string) => {
    if (!userPreferences) return true;
    switch (component) {
      case 'neo4j':
        return userPreferences.neo4j_enabled;
      case 'qdrant':
        return userPreferences.qdrant_enabled;
      case 'elasticsearch':
        return userPreferences.elasticsearch_enabled;
      default:
        return true;
    }
  };

  const handleToggleDataSource = (component: string) => {
    const currentEnabled = getDataSourceEnabled(component);
    
    // If trying to disable Neo4j, show confirmation alert
    if (component === 'neo4j' && currentEnabled) {
      const isConfirmed = window.confirm('The Graph Database serves as the primary data source. Disabling it may affect system functionality. Do you want to proceed?');
      if (!isConfirmed) {
        return; // User cancelled, don't proceed with disabling
      }
    }
    
    updateUserPreference(component, !currentEnabled);
  };

  if (authLoading) {
    return (
      <Box p={4} bg={colors.cardBg} borderRadius="lg" borderWidth={1} borderColor={colors.border}>
        <Text color={colors.text}>Loading...</Text>
      </Box>
    );
  }

  if (!currentUser) {
    return (
      <Box p={4} bg={colors.cardBg} borderRadius="lg" borderWidth={1} borderColor={colors.border}>
        <Text color={colors.text}>Please sign in to view system health.</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4} bg={colors.cardBg} borderRadius="lg" borderWidth={1} borderColor={colors.border}>
        <Text color="red.400">{error}</Text>
      </Box>
    );
  }

  return (
    <Box 
      p={3} 
      bg={colors.cardBg} 
      borderRadius="lg" 
      borderWidth={1} 
      borderColor={colors.border}
      boxShadow="sm"
      _hover={{
        borderColor: colors.primary,
        transform: 'translateY(-1px)',
      }}
      transition="all 0.2s ease-in-out"
    >
      <VStack spacing={2} align="stretch">
        <HStack justify="space-between" py={1}>
          <Text fontSize="sm" fontWeight="bold" color={colors.text}>System Health</Text>
          <Icon
            as={FiRefreshCw}
            size="sm"
            color={colors.text}
            cursor="pointer"
            onClick={fetchHealthStatus}
            animation={loading ? 'spin 1s linear infinite' : 'none'}
            _hover={{ color: colors.primary }}
            transition="color 0.2s ease-in-out"
          />
        </HStack>
        {healthData && (
          <VStack spacing={1} align="stretch">
            {(() => {
              console.log('SystemHealth: Rendering with data:', healthData);
              console.log('SystemHealth: Available components:', Object.keys(healthData.components));
              return null;
            })()}
            {[
              'neo4j',
              'qdrant',
              'elasticsearch',
              'postgres',
              'openai'
            ].map((component) => {
              console.log(`SystemHealth: Processing component: ${component}`);
              const status = healthData.components[component as keyof typeof healthData.components];
              console.log(`SystemHealth: Status for ${component}:`, status);
              
              if (component === 'postgres') {
                console.log('SystemHealth: POSTGRES DEBUG - Component:', component);
                console.log('SystemHealth: POSTGRES DEBUG - Status:', status);
                console.log('SystemHealth: POSTGRES DEBUG - Components object:', healthData.components);
                console.log('SystemHealth: POSTGRES DEBUG - Has postgres key:', 'postgres' in healthData.components);
              }
              
              if (!status) {
                console.log(`SystemHealth: Skipping ${component} - no status`);
                return null;
              }
              
              console.log(`SystemHealth: Rendering component ${component} with status:`, status.status);
              
              const isDataSource = isDataSourceComponent(component);
              const isEnabled = getDataSourceEnabled(component);
              const isUpdating = updatingPreferences === component;
              
              console.log(`SystemHealth: ${component} - isDataSource: ${isDataSource}, isEnabled: ${isEnabled}, isUpdating: ${isUpdating}`);
              
              return (
                <HStack 
                  key={component} 
                  spacing={2} 
                  py={2} 
                  px={2}
                  borderRadius="md"
                  bg={colors.inputBg}
                  borderWidth={1}
                  borderColor={colors.inputBorder}
                  _hover={{
                    borderColor: colors.primary,
                    bg: colors.gradientLight,
                  }}
                  transition="all 0.2s ease-in-out"
                  alignItems="center"
                >
                  <Icon 
                    as={getComponentIcon(component)} 
                    size="sm" 
                    color={colors.text}
                  />
                  <Text 
                    flex={1} 
                    fontSize="sm" 
                    fontWeight="medium"
                    color={colors.text}
                  >
                    {getComponentLabel(component)}
                  </Text>
                  <Tooltip label={`${status.status} - ${getContextStatusTooltip(status.context_status)}`}>
                    <Box
                      w={3}
                      h={3}
                      borderRadius="full"
                      bg={
                        isDataSource && !isEnabled 
                          ? 'gray.400' 
                          : status.status === 'healthy' 
                            ? 'green.500' 
                            : 'red.500'
                      }
                      borderWidth={1}
                      borderColor={colors.border}
                    />
                  </Tooltip>
                  {isDataSource && (
                    <HStack spacing={2} ml={2}>
                      {isUpdating ? (
                        <Spinner size="sm" color={colors.primary} />
                      ) : (
                        <Switch
                          size="md"
                          isChecked={isEnabled}
                          onChange={() => handleToggleDataSource(component)}
                          colorScheme={isEnabled ? 'green' : 'gray'}
                        />
                      )}
                    </HStack>
                  )}
                </HStack>
              );
            })}
            <Text fontSize="xs" color={colors.text + '80'} mt={1} textAlign="center">
              Last updated: {new Date(healthData.timestamp).toLocaleTimeString()}
            </Text>
          </VStack>
        )}
        

      </VStack>
    </Box>
  );
};

export default SystemHealth; 