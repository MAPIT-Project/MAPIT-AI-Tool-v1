import React, { useEffect, useRef, useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Box,
  Text,
  Select,
  VStack,
  HStack,
  Badge,
  useColorModeValue,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Switch,
} from '@chakra-ui/react';
import { useThemeColors } from '../hooks/useThemeColors';
import L from 'leaflet';

interface HeatmapData {
  country: string;
  projects: number;
  ec_sum: number;
}

interface HeatmapModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: HeatmapData[];
  luceneQuery: string;
  metric: string;
}

// Country code to full name mapping
const getCountryFullName = (countryCode: string): string => {
  const countryNames: { [key: string]: string } = {
    'DE': 'Germany',
    'FR': 'France',
    'IT': 'Italy',
    'ES': 'Spain',
    'NL': 'Netherlands',
    'BE': 'Belgium',
    'AT': 'Austria',
    'SE': 'Sweden',
    'DK': 'Denmark',
    'FI': 'Finland',
    'NO': 'Norway',
    'CH': 'Switzerland',
    'PL': 'Poland',
    'CZ': 'Czech Republic',
    'TR': 'Turkey',
    'HU': 'Hungary',
    'RO': 'Romania',
    'BG': 'Bulgaria',
    'HR': 'Croatia',
    'SI': 'Slovenia',
    'SK': 'Slovakia',
    'EE': 'Estonia',
    'EL': 'Greece',
    'RS': 'Serbia',
    'ME': 'Montenegro',
    'AL': 'Albania',
    'MK': 'North Macedonia',
    'BA': 'Bosnia and Herzegovina',
    'XK': 'Kosovo',
    'UA': 'Ukraine',
    'MD': 'Moldova',
    'AM': 'Armenia',
    'AZ': 'Azerbaijan',
    'GE': 'Georgia',
    'KZ': 'Kazakhstan',
    'KG': 'Kyrgyzstan',
    'US': 'United States',
    'CA': 'Canada',
    'MX': 'Mexico',
    'BR': 'Brazil',
    'AR': 'Argentina',
    'CO': 'Colombia',
    'PE': 'Peru',
    'LV': 'Latvia',
    'LT': 'Lithuania',
    'IE': 'Ireland',
    'PT': 'Portugal',
    'GR': 'Greece',
    'CY': 'Cyprus',
    'MT': 'Malta',
    'LU': 'Luxembourg',
    'UK': 'United Kingdom',
  };
  
  const fullName = countryNames[countryCode];
  return fullName ? `${fullName} (${countryCode})` : countryCode;
};

const HeatmapModal: React.FC<HeatmapModalProps> = ({
  isOpen,
  onClose,
  data,
  luceneQuery,
  metric,
}) => {
  console.log('HeatmapModal props:', { isOpen, dataLength: data.length, data, luceneQuery, metric });
  
  const [selectedMetric, setSelectedMetric] = useState(metric);
  const [hoveredCountry, setHoveredCountry] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'map' | 'table'>('map'); // Default to map view
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const borderColor = useColorModeValue('gray.300', 'gray.600');
  const colors = useThemeColors();

  const getTotalProjects = () => data.reduce((sum, item) => sum + item.projects, 0);
  const getTotalFunding = () => data.reduce((sum, item) => sum + item.ec_sum, 0);

  const getColorForValue = (value: number, maxValue: number) => {
    if (maxValue === 0) return '#fef5e7';
    const ratio = value / maxValue;
    if (ratio < 0.2) return '#fed7aa'; // Light orange
    if (ratio < 0.4) return '#fdba74'; // Orange
    if (ratio < 0.6) return '#fb923c'; // Dark orange
    if (ratio < 0.8) return '#ea580c'; // Red-orange
    return '#dc2626'; // Red
  };

  const dataMap = new Map();
  data.forEach(item => {
    dataMap.set(item.country, item);
  });

  const maxValue = Math.max(...data.map(item => selectedMetric === 'projects' ? item.projects : item.ec_sum), 1);

  // Simple country coordinates mapping (you can expand this)
  const getCountryCoordinates = (countryCode: string): [number, number] | null => {
    const coordinates: { [key: string]: [number, number] } = {
      'DE': [51.1657, 10.4515], // Germany
      'FR': [46.2276, 2.2137],  // France
      'IT': [41.8719, 12.5674], // Italy
      'ES': [40.4637, -3.7492], // Spain
      'NL': [52.1326, 5.2913],  // Netherlands
      'BE': [50.8503, 4.3517],  // Belgium
      'AT': [47.5162, 14.5501], // Austria
      'SE': [60.1282, 18.6435], // Sweden
      'DK': [56.2639, 9.5018],  // Denmark
      'FI': [61.9241, 25.7482], // Finland
      'NO': [60.4720, 8.4689],  // Norway
      'CH': [46.8182, 8.2275],  // Switzerland
      'PL': [51.9194, 19.1451], // Poland
      'CZ': [49.8175, 15.4730], // Czech Republic
      'HU': [47.1625, 19.5033], // Hungary
      'RO': [45.9432, 24.9668], // Romania
      'BG': [42.7339, 25.4858], // Bulgaria
      'HR': [45.1000, 15.2000], // Croatia
      'SI': [46.0569, 14.5058], // Slovenia
      'SK': [48.6690, 19.6990], // Slovakia
      'EE': [58.5953, 25.0136], // Estonia
      'LV': [56.8796, 24.6032], // Latvia
      'LT': [55.1694, 23.8813], // Lithuania
      'IE': [53.1424, -7.6921], // Ireland
      'PT': [39.3999, -8.2245], // Portugal
      'GR': [39.0742, 21.8243], // Greece
      'CY': [35.1264, 33.4299], // Cyprus
      'MT': [35.9375, 14.3754], // Malta
      'LU': [49.8153, 6.1296],  // Luxembourg
      'UK': [55.3781, -3.4360], // United Kingdom
    };
    return coordinates[countryCode] || null;
  };

  useEffect(() => {
    console.log('HeatmapModal useEffect triggered:', { isOpen, dataLength: data.length, viewMode });
    if (!isOpen || viewMode !== 'map') {
      console.log('Modal not open or not in map mode');
      return;
    }

    // Wait for container to be available and have dimensions
    const initMap = () => {
      if (!mapContainer.current) {
        console.log('Container not ready, retrying...');
        setTimeout(initMap, 100);
        return;
      }

      const container = mapContainer.current;
      console.log('Container dimensions check:', container.offsetWidth, container.offsetHeight);
      if (container.offsetWidth === 0 || container.offsetHeight === 0) {
        console.log('Container has no dimensions, retrying...');
        setTimeout(initMap, 100);
        return;
      }

      console.log('Container ready, initializing map...');
      console.log('Container dimensions:', container.offsetWidth, container.offsetHeight);

      // Clean up previous map
      if (map.current) {
        console.log('Removing previous map');
        map.current.remove();
        map.current = null;
      }

      setMapError(null);
      setMapLoading(true);

      try {
        console.log('Initializing Leaflet map...');
        
        // Create map with OpenStreetMap tiles (free)
        map.current = L.map(container, {
          center: [50, 10], // Center on Europe
          zoom: 4,
          maxZoom: 8,
          minZoom: 2
        });

        // Add OpenStreetMap tile layer (free)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors',
          maxZoom: 18
        }).addTo(map.current);

        console.log('Data to process:', data);
        
        let countriesFound = 0;
        // Create a simple choropleth visualization using circles
        data.forEach((item: HeatmapData) => {
          console.log('Processing country:', item.country);
          // Get country coordinates (simplified - you might want to use a proper country coordinates database)
          const countryCoords = getCountryCoordinates(item.country);
          console.log('Country coordinates:', countryCoords);
          if (countryCoords) {
            countriesFound++;
            const value = selectedMetric === 'projects' ? item.projects : item.ec_sum;
            const radius = Math.max(5, Math.min(30, (value / maxValue) * 25));
            const color = getColorForValue(value, maxValue);
            
            const circle = L.circleMarker(countryCoords, {
              radius: radius,
              fillColor: color,
              color: '#333',
              weight: 1,
              opacity: 1,
              fillOpacity: 0.8
            }).addTo(map.current!);

            // Add popup with country info
            circle.bindPopup(`
              <strong>${getCountryFullName(item.country)}</strong><br>
              Projects: ${item.projects}<br>
              Funding: €${(item.ec_sum / 1000000).toFixed(1)}M
            `);

            // Add hover effect
            circle.on('mouseover', () => {
              setHoveredCountry(item.country);
              circle.setStyle({ fillOpacity: 1 });
            });

            circle.on('mouseout', () => {
              setHoveredCountry(null);
              circle.setStyle({ fillOpacity: 0.8 });
            });
          }
        });

        console.log('Leaflet map initialized successfully');
        console.log('Countries found on map:', countriesFound);
        
        if (countriesFound === 0) {
          console.log('No countries found on map, showing table view');
          setMapError('No geographic data found for the selected countries. Using table view instead.');
          setViewMode('table');
        }
        
        setMapLoading(false);
        
        // Add a timeout to ensure map is properly loaded
        setTimeout(() => {
          if (map.current && !map.current.getSize()) {
            console.log('Map not properly loaded, forcing table view');
            setMapError('Map failed to load properly. Using table view instead.');
            setViewMode('table');
          }
        }, 2000);

      } catch (error) {
        console.error('Error initializing Leaflet map:', error);
        setMapError('Failed to initialize map. Using table view instead.');
        setViewMode('table');
        setMapLoading(false);
      }
    };

    // Start the initialization process
    initMap();

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [isOpen, data, selectedMetric, maxValue, viewMode]);



  // Table view component
  const TableView = () => (
    <Box h="100%" display="flex" flexDirection="column">
      <Text fontSize="lg" fontWeight="bold" mb={4} flexShrink={0} color={colors.text}>
        Geographic Data Table View
      </Text>
      <Box 
        h="400px"
        overflowY="auto" 
        border="1px solid"
        borderColor={borderColor}
        borderRadius="md"
        p={2}
      >
        <Table variant="simple" size="sm">
          <Thead position="sticky" top={0} bg={colors.cardBg} zIndex={1}>
            <Tr>
              <Th color={colors.text}>Country</Th>
              <Th color={colors.text}>Projects</Th>
              <Th color={colors.text}>EC Funding (€)</Th>
              <Th color={colors.text}>Color</Th>
            </Tr>
          </Thead>
          <Tbody>
            {data.map((item) => (
              <Tr key={item.country}>
                <Td fontWeight="bold" color={colors.text}>{getCountryFullName(item.country)}</Td>
                <Td color={colors.text}>{item.projects}</Td>
                <Td color={colors.text}>€{(item.ec_sum / 1000000).toFixed(1)}M</Td>
                <Td>
                  <Box
                    w="20px"
                    h="12px"
                    bg={getColorForValue(
                      selectedMetric === 'projects' ? item.projects : item.ec_sum,
                      maxValue
                    )}
                    border="1px solid"
                    borderColor={borderColor}
                  />
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
    </Box>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl">
      <ModalOverlay />
      <ModalContent maxW="90vw" maxH="95vh" bg={colors.cardBg} borderColor={colors.cardBorder}>
        <ModalHeader>
          <VStack align="start" spacing={2}>
            <Text fontSize="xl" fontWeight="bold" color={colors.text}>
              Geography × Topic Heatmap
            </Text>
            <Text fontSize="sm" color={colors.text + '80'}>
              Query: "{luceneQuery}"
            </Text>
            <HStack spacing={4}>
              <Badge colorScheme="blue">
                {data.length} Countries
              </Badge>
              <Badge colorScheme="green">
                {getTotalProjects()} Total Projects
              </Badge>
              <Badge colorScheme="purple">
                €{(getTotalFunding() / 1000000).toFixed(1)}M Total Funding
              </Badge>
            </HStack>
          </VStack>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody p={0}>
          <Box p={4} borderBottom="1px" borderColor={borderColor}>
            <HStack spacing={6} align="center" w="100%">
              {/* Color by selector */}
              <HStack spacing={4} align="center">
                <Text fontWeight="medium" color={colors.text}>Color by:</Text>
                                  <Select
                    value={selectedMetric}
                    onChange={(e) => setSelectedMetric(e.target.value)}
                    w="150px"
                    bg={colors.inputBg}
                    borderColor={colors.inputBorder}
                    color={colors.text}
                    _placeholder={{ color: colors.text + '60' }}
                  >
                    <option value="projects"># of Projects</option>
                    <option value="ec_sum">EC Funding (€)</option>
                  </Select>
              </HStack>
              
              {/* Color Legend - always visible */}
              <HStack spacing={2} align="center">
                <Text fontSize="xs" color={colors.text}>Low</Text>
                <HStack spacing={1}>
                  <Box w="8px" h="12px" bg="#fed7aa" border="1px solid" borderColor={borderColor} />
                  <Box w="8px" h="12px" bg="#fdba74" border="1px solid" borderColor={borderColor} />
                  <Box w="8px" h="12px" bg="#fb923c" border="1px solid" borderColor={borderColor} />
                  <Box w="8px" h="12px" bg="#ea580c" border="1px solid" borderColor={borderColor} />
                  <Box w="8px" h="12px" bg="#dc2626" border="1px solid" borderColor={borderColor} />
                </HStack>
                <Text fontSize="xs" color={colors.text}>High</Text>
              </HStack>
              
              {/* View toggle */}
              <HStack spacing={3} align="center" ml="auto">
                <Text fontSize="sm" color={colors.text}>Table View</Text>
                <Switch
                  isChecked={viewMode === 'map'}
                  onChange={(e) => {
                    const newMode = e.target.checked ? 'map' : 'table';
                    setViewMode(newMode);
                    setMapError(null);
                  }}
                  colorScheme="blue"
                  size="md"
                />
                <Text fontSize="sm" color={colors.text}>Map View</Text>
              </HStack>
            </HStack>
          </Box>
          
          <Box p={4} position="relative" maxH="calc(95vh - 220px)" overflow="hidden">
            {viewMode === 'table' ? (
              <Box h="100%" display="flex" flexDirection="column">
                <Box flex="1" minH="0">
                  <TableView />
                </Box>
              </Box>
            ) : (
              <Box
                w="100%"
                h="100%"
                border="1px solid"
                borderColor={borderColor}
                borderRadius="md"
                overflow="hidden"
                position="relative"
                minH="400px"
              >
                {mapError && (
                  <Box
                    position="absolute"
                    top="10px"
                    left="10px"
                    right="10px"
                    zIndex={30}
                    p={3}
                    bg="yellow.50"
                    border="1px solid"
                    borderColor="yellow.200"
                    borderRadius="md"
                    _dark={{
                      bg: 'yellow.900',
                      borderColor: 'yellow.700',
                    }}
                  >
                    <Text fontSize="sm" color="yellow.800" _dark={{ color: 'yellow.200' }}>
                      {mapError}
                    </Text>
                  </Box>
                )}
                {mapLoading && (
                  <Box
                    position="absolute"
                    top="50%"
                    left="50%"
                    transform="translate(-50%, -50%)"
                    zIndex={20}
                    bg="white"
                    p={4}
                    borderRadius="md"
                    boxShadow="lg"
                    border="1px solid"
                    borderColor={borderColor}
                  >
                    <Text>Loading map...</Text>
                  </Box>
                )}
                <div ref={mapContainer} style={{ width: '100%', height: '450px' }} />

                {/* Tooltip */}
                {hoveredCountry && dataMap.has(hoveredCountry) && (
                  <Box
                    position="absolute"
                    top="10px"
                    left="10px"
                    bg="white"
                    p={3}
                    borderRadius="md"
                    boxShadow="lg"
                    border="1px solid"
                    borderColor={borderColor}
                    zIndex={10}
                  >
                    <Text fontWeight="bold" fontSize="sm">
                      {getCountryFullName(hoveredCountry)}
                    </Text>
                    <Text fontSize="sm">
                      Projects: {dataMap.get(hoveredCountry).projects}
                    </Text>
                    <Text fontSize="sm">
                      Funding: €{(dataMap.get(hoveredCountry).ec_sum / 1000000).toFixed(1)}M
                    </Text>
                  </Box>
                )}
              </Box>
            )}

            {data.length === 0 && (
              <Box textAlign="center" py={8}>
                <Text color="gray.500">No geographic data available for this query.</Text>
              </Box>
            )}
          </Box>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

export default HeatmapModal;
