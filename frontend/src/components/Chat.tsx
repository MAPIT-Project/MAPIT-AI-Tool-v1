/**
 * Chat Component with Node Visualizer Integration
 * 
 * This component includes a new feature that automatically detects project acronyms
 * in chat responses and adds clickable node visualizer icons next to them.
 * 
 * Feature Details:
 * - Extracts project acronyms and node IDs from Neo4j, Qdrant, and Elasticsearch context data
 * - Adds 🔍 icons next to project acronyms in the response text
 * - Clicking the icon opens a new window with an interactive node visualization
 * - The visualization shows the project and its connected entities (organizations, publications, etc.)
 * 
 * Example: If the response contains "TWINVEST project" and TWINVEST is found in the context data
 * with a node ID, it will display as "TWINVEST 🔍 project" where the 🔍 is clickable.
 */

import { useState, useEffect, useRef } from 'react'
import {
  Box,
  VStack,
  Input,
  Textarea,
  Button,
  Text,
  Flex,
  Image,
  HStack,
  IconButton,
  useToast,
  Tooltip,
  UnorderedList,
  ListItem,
  Icon,
  Badge,
  useDisclosure,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  Divider,
  useBreakpointValue,
} from '@chakra-ui/react'
import { FiPlus, FiDatabase, FiServer, FiGlobe, FiCpu, FiClock, FiSend, FiStopCircle, FiX, FiEdit2, FiSearch, FiCopy, FiHash, FiMenu, FiBarChart, FiUsers, FiGitBranch, FiFileText, FiUser } from 'react-icons/fi'
import { Navbar } from './Navbar'
import mapitLogo from '../assets/mapit_logo_no_bg.png'

// Animated Spinner Component
const AnimatedSpinner = ({ size = "xs", color = "blue.500" }: { size?: string, color?: string }) => (
  <Box
    display="inline-flex"
    alignItems="center"
    justifyContent="center"
    animation="spin 1s linear infinite"
    sx={{
      '@keyframes spin': {
        '0%': { transform: 'rotate(0deg)' },
        '100%': { transform: 'rotate(360deg)' }
      }
    }}
  >
    <Box
      width={size}
      height={size}
      borderRadius="50%"
      border="2px solid"
      borderColor={`${color}20`}
      borderTopColor={color}
    />
  </Box>
)
import NodeVisualizer from './ProjectVisualizer'
import CoParticipationBox from './CoParticipationBox'
import PartnerFinderBox from './PartnerFinderBox'
import PartnerResultsModal from './PartnerResultsModal'
import HeatmapModal from './HeatmapModal'
import { useThemeColors } from '../hooks/useThemeColors'
import DOMPurify from 'dompurify'
import { apiGet, apiPost, apiPut, apiDelete, apiStream } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import SystemHealthComponent from './SystemHealth'

// Utility function to truncate long titles
const truncateTitle = (title: string, maxLength: number = 60): string => {
  if (title.length <= maxLength) {
    return title;
  }
  
  // Try to truncate at a word boundary
  const truncated = title.substring(0, maxLength);
  const lastSpaceIndex = truncated.lastIndexOf(' ');
  
  if (lastSpaceIndex > maxLength * 0.7) { // If we can break at a word boundary
    return truncated.substring(0, lastSpaceIndex) + '...';
  }
  
  return truncated + '...';
};

// Helper function to extract project information including acronym
const extractProjectInfo = (item: any, key: string): { title: string; acronym?: string; linkType: string } => {
  let title = item[key]; // Default to DOI value
  let linkType = "DOI"; // Default type
  let acronym: string | undefined;
  
  // Determine if this is a source or neighbor field
  const isSource = key.toLowerCase().includes('source');
  const isNeighbor = key.toLowerCase().includes('neighbor');
  
  // Get corresponding title and type based on source/neighbor
  if (isSource) {
    if (item.sourceTitle) title = item.sourceTitle;
    if (item.sourceType) linkType = item.sourceType;
    if (item.sourceAcronym) acronym = item.sourceAcronym;
  } else if (isNeighbor) {
    if (item.neighborTitle) title = item.neighborTitle;
    if (item.neighborType) linkType = item.neighborType;
    if (item.neighborAcronym) acronym = item.neighborAcronym;
  } else {
    // Look for title-related keys in the same item
    Object.keys(item).forEach(titleKey => {
      if (titleKey.toLowerCase().includes('title') && item[titleKey]) {
        title = item[titleKey];
      } else if (titleKey.toLowerCase().includes('name') && item[titleKey] && title === item[key]) {
        title = item[titleKey];
      } else if (titleKey.toLowerCase().includes('id') && item[titleKey] && title === item[key]) {
        title = item[titleKey];
      } else if (titleKey.toLowerCase().includes('label') && item[titleKey] && title === item[key]) {
        title = item[titleKey];
      }
    });
    
    // Look for acronym-related keys
    Object.keys(item).forEach(acronymKey => {
      if (acronymKey.toLowerCase().includes('acronym') && item[acronymKey]) {
        acronym = item[acronymKey];
      }
    });
    
    // Try to find the actual type/label from Neo4j data
    if (item.type) linkType = item.type;
    else if (item.label) linkType = item.label;
    else if (item.category) linkType = item.category;
    // Special case: if it's a grantDoi, it's likely a Project
    else if (key.toLowerCase().includes('grantdoi')) {
      linkType = "Project";
    }
  }
  
  return { title, acronym, linkType };
};

// Function to generate links from context data
const generateLinksFromContext = (contextData: any, content?: string): any[] => {
  const links: any[] = [];
  
  if (!contextData) return links;
  
  // Extract links from Neo4j results
  if (contextData.neo4j && Array.isArray(contextData.neo4j)) {
    contextData.neo4j.forEach((item: any) => {
      // Extract DOI links from Neo4j data (check for any field containing "doi")
      Object.keys(item).forEach(key => {
        if (key.toLowerCase().includes('doi') && item[key]) {
          const { title, acronym, linkType } = extractProjectInfo(item, key);
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "doi",
            url: `https://doi.org/${item[key]}`,
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "neo4j"
          });
        }
      });
      
      // Extract URL links from Neo4j data (check for any field containing "url")
      Object.keys(item).forEach(key => {
        if (key.toLowerCase().includes('url') && item[key]) {
          const { title, acronym, linkType } = extractProjectInfo(item, key);
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "url",
            url: item[key],
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "neo4j"
          });
        }
      });
    });
  }
  
  // Extract links from Qdrant results
  if (contextData.qdrant && Array.isArray(contextData.qdrant)) {
    contextData.qdrant.forEach((doc: any) => {
      // Extract DOI links from Qdrant data (check for any field containing "doi")
      Object.keys(doc).forEach(key => {
        if (key.toLowerCase().includes('doi') && doc[key]) {
          // Extract project information
          let title = doc[key]; // Default to DOI value
          let linkType = "DOI"; // Default type
          let acronym: string | undefined;
          
          // Look for title-related keys in the same doc
          Object.keys(doc).forEach(titleKey => {
            if (titleKey.toLowerCase().includes('title') && doc[titleKey]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('name') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('id') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('label') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('content') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey].substring(0, 50) + '...';
            }
          });
          
          // Look for acronym-related keys
          Object.keys(doc).forEach(acronymKey => {
            if (acronymKey.toLowerCase().includes('acronym') && doc[acronymKey]) {
              acronym = doc[acronymKey];
            }
          });
          
          // Try to find the actual type/label from data
          if (doc.type) linkType = doc.type;
          else if (doc.label) linkType = doc.label;
          else if (doc.category) linkType = doc.category;
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "doi",
            url: `https://doi.org/${doc[key]}`,
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "qdrant"
          });
        }
      });
      
      // Extract URL links from Qdrant data (check for any field containing "url")
      Object.keys(doc).forEach(key => {
        if (key.toLowerCase().includes('url') && doc[key]) {
          // Extract project information
          let title = doc[key]; // Default to URL value
          let linkType = "URL"; // Default type
          let acronym: string | undefined;
          
          // Look for title-related keys in the same doc
          Object.keys(doc).forEach(titleKey => {
            if (titleKey.toLowerCase().includes('title') && doc[titleKey]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('name') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('id') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('label') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('content') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey].substring(0, 50) + '...';
            }
          });
          
          // Look for acronym-related keys
          Object.keys(doc).forEach(acronymKey => {
            if (acronymKey.toLowerCase().includes('acronym') && doc[acronymKey]) {
              acronym = doc[acronymKey];
            }
          });
          
          // Try to find the actual type/label from data
          if (doc.type) linkType = doc.type;
          else if (doc.label) linkType = doc.label;
          else if (doc.category) linkType = doc.category;
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "url",
            url: doc[key],
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "qdrant"
          });
        }
      });
    });
  }
  
  // Extract links from Elasticsearch results
  if (contextData.elasticsearch && Array.isArray(contextData.elasticsearch)) {
    contextData.elasticsearch.forEach((doc: any) => {
      // Extract DOI links from Elasticsearch data (check for any field containing "doi")
      Object.keys(doc).forEach(key => {
        if (key.toLowerCase().includes('doi') && doc[key]) {
          // Extract project information
          let title = doc[key]; // Default to DOI value
          let linkType = "DOI"; // Default type
          let acronym: string | undefined;
          
          // Look for title-related keys in the same doc
          Object.keys(doc).forEach(titleKey => {
            if (titleKey.toLowerCase().includes('title') && doc[titleKey]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('name') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('id') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('label') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('content') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey].substring(0, 50) + '...';
            }
          });
          
          // Look for acronym-related keys
          Object.keys(doc).forEach(acronymKey => {
            if (acronymKey.toLowerCase().includes('acronym') && doc[acronymKey]) {
              acronym = doc[acronymKey];
            }
          });
          
          // Try to find the actual type/label from data
          if (doc.type) linkType = doc.type;
          else if (doc.label) linkType = doc.label;
          else if (doc.category) linkType = doc.category;
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "doi",
            url: `https://doi.org/${doc[key]}`,
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "elasticsearch"
          });
        }
      });
      
      // Extract URL links from Elasticsearch data (check for any field containing "url")
      Object.keys(doc).forEach(key => {
        if (key.toLowerCase().includes('url') && doc[key]) {
          // Extract project information
          let title = doc[key]; // Default to URL value
          let linkType = "URL"; // Default type
          let acronym: string | undefined;
          
          // Look for title-related keys in the same doc
          Object.keys(doc).forEach(titleKey => {
            if (titleKey.toLowerCase().includes('title') && doc[titleKey]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('name') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('id') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('label') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey];
            } else if (titleKey.toLowerCase().includes('content') && doc[titleKey] && title === doc[key]) {
              title = doc[titleKey].substring(0, 50) + '...';
            }
          });
          
          // Look for acronym-related keys
          Object.keys(doc).forEach(acronymKey => {
            if (acronymKey.toLowerCase().includes('acronym') && doc[acronymKey]) {
              acronym = doc[acronymKey];
            }
          });
          
          // Try to find the actual type/label from data
          if (doc.type) linkType = doc.type;
          else if (doc.label) linkType = doc.label;
          else if (doc.category) linkType = doc.category;
          
          // Format the title based on whether it's a project and has an acronym
          let formattedTitle = title;
          let formattedOriginalTitle = title;
          
          if (linkType === "Project" && acronym) {
            formattedTitle = `${acronym}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${acronym}: ${title}`;
          } else {
            formattedTitle = `${linkType}: ${truncateTitle(title)}`;
            formattedOriginalTitle = `${linkType}: ${title}`;
          }
          
          links.push({
            type: "url",
            url: doc[key],
            label: linkType,
            title: formattedTitle,
            originalTitle: formattedOriginalTitle,
            source: "elasticsearch"
          });
        }
      });
    });
  }
  
  // Extract links from response content
  if (content) {
    // Extract DOI links from content (look for DOI patterns)
    const doiPattern = /10\.\d{4,}(?:\.\d+)*\/\S+(?:\s|$)/g;
    const doiMatches = content.match(doiPattern);
    if (doiMatches) {
      doiMatches.forEach(doi => {
        // Try to find a better title by looking for context around the DOI
        const doiTrimmed = doi.trim();
        const contextBefore = content.substring(Math.max(0, content.indexOf(doiTrimmed) - 50), content.indexOf(doiTrimmed));
        const contextAfter = content.substring(content.indexOf(doiTrimmed) + doiTrimmed.length, content.indexOf(doiTrimmed) + doiTrimmed.length + 50);
        
        let title = doiTrimmed; // Default to DOI
        if (contextBefore.includes('title') || contextBefore.includes('paper') || contextBefore.includes('article')) {
          title = contextBefore.split(' ').slice(-3).join(' ') + ' ' + doiTrimmed;
        } else if (contextAfter.includes('title') || contextAfter.includes('paper') || contextAfter.includes('article')) {
          title = doiTrimmed + ' ' + contextAfter.split(' ').slice(0, 3).join(' ');
        }
        
        links.push({
          type: "doi",
          url: `https://doi.org/${doiTrimmed}`,
          label: "DOI",
          title: `DOI: ${truncateTitle(title.trim())}`,
          originalTitle: `DOI: ${title.trim()}`,
          source: "content"
        });
      });
    }
    
    // Extract URL links from content (look for URL patterns)
    const urlPattern = /https?:\/\/[^\s]+/g;
    const urlMatches = content.match(urlPattern);
    if (urlMatches) {
      urlMatches.forEach(url => {
        const urlTrimmed = url.trim();
        // Try to find a better title by looking for context around the URL
        const contextBefore = content.substring(Math.max(0, content.indexOf(urlTrimmed) - 50), content.indexOf(urlTrimmed));
        const contextAfter = content.substring(content.indexOf(urlTrimmed) + urlTrimmed.length, content.indexOf(urlTrimmed) + urlTrimmed.length + 50);
        
        let title = urlTrimmed; // Default to URL
        if (contextBefore.includes('website') || contextBefore.includes('link') || contextBefore.includes('page')) {
          title = contextBefore.split(' ').slice(-3).join(' ') + ' ' + urlTrimmed.split('/').pop();
        } else if (contextAfter.includes('website') || contextAfter.includes('link') || contextAfter.includes('page')) {
          title = urlTrimmed.split('/').pop() + ' ' + contextAfter.split(' ').slice(0, 3).join(' ');
        } else {
          // Use domain name as title
          try {
            const domain = new URL(urlTrimmed).hostname;
            title = domain;
          } catch {
            title = urlTrimmed.split('/').pop() || urlTrimmed;
          }
        }
        
        links.push({
          type: "url",
          url: urlTrimmed,
          label: "URL",
          title: `URL: ${truncateTitle(title.trim())}`,
          originalTitle: `URL: ${title.trim()}`,
          source: "content"
        });
      });
    }
  }
  
  // Remove duplicates based on URL
  const uniqueLinks = links.filter((link, index, self) => 
    index === self.findIndex(l => l.url === link.url)
  );
  
  return uniqueLinks;
};

// References Display Component
const ReferencesDisplay: React.FC<{ contextData: any; content?: string }> = ({ contextData, content }) => {
  const colors = useThemeColors();
  
  // Generate links from context data
  const generatedLinks = generateLinksFromContext(contextData, content);
  
  // Debug generated links
  console.log('ReferencesDisplay contextData:', contextData);
  console.log('ReferencesDisplay generatedLinks:', generatedLinks);
  console.log('ReferencesDisplay generatedLinks length:', generatedLinks.length);
  
  if (generatedLinks.length === 0) {
    return null;
  }
  
  return (
    <Box
      mt={3}
      p={3}
      bg={colors.cardBg}
      borderRadius="md"
      border="1px solid"
      borderColor={colors.cardBorder}
      boxShadow={colors.shadow}
    >
      <VStack spacing={2} align="stretch">
        <HStack justify="space-between" align="center">
          <HStack spacing={2} align="center">
            <Icon as={FiFileText} color={colors.primary} boxSize={4} />
            <Text fontSize="md" fontWeight="bold" color={colors.text}>
              References
            </Text>
          </HStack>
          <Badge colorScheme="blue" variant="subtle" fontSize="xs">
            {generatedLinks.length} reference{generatedLinks.length !== 1 ? 's' : ''}
          </Badge>
        </HStack>
        
        <VStack spacing={1} align="stretch">
          {generatedLinks.map((link, index) => {
            // Check if the title is truncated (ends with "...")
            const isTruncated = link.title.endsWith('...');
            
            return (
              <Tooltip
                key={index}
                label={isTruncated && link.originalTitle ? link.originalTitle : undefined}
                placement="top"
                hasArrow
                bg="gray.800"
                color="white"
                borderRadius="md"
                fontSize="sm"
                maxW="300px"
                isDisabled={!isTruncated}
              >
                <Button
                  as="a"
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="sm"
                  variant="outline"
                  colorScheme={link.type === "doi" ? "purple" : link.type === "file" ? "green" : "blue"}
                  leftIcon={<Icon as={FiSearch} boxSize={3} />}
                  _hover={{
                    bg: link.type === "doi" ? 'purple.50' : link.type === "file" ? 'green.50' : 'blue.50',
                    borderColor: link.type === "doi" ? 'purple.300' : link.type === "file" ? 'green.300' : 'blue.300',
                    transform: 'translateY(-1px)',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                  transition="all 0.2s ease-in-out"
                  textAlign="left"
                  justifyContent="flex-start"
                  whiteSpace="normal"
                  height="auto"
                  minH="32px"
                  py={1}
                  px={2}
                  fontSize="sm"
                >
                  {link.title}
                </Button>
              </Tooltip>
            );
          })}
        </VStack>
      </VStack>
    </Box>
  );
};

// Chart Display Component
const ChartDisplay: React.FC<{ chartData: any }> = ({ chartData }) => {
  const colors = useThemeColors();
  
  console.log('ChartDisplay component called with chartData:', chartData);
  
  if (!chartData || !chartData.image_base64) {
    console.log('ChartDisplay: No chartData or image_base64, returning null');
    return null;
  }
  
  return (
    <Box
      mt={4}
      p={4}
      bg={colors.cardBg}
      borderRadius="lg"
      border="1px solid"
      borderColor={colors.cardBorder}
      boxShadow={colors.shadow}
    >
      <VStack spacing={3} align="stretch">
        <HStack justify="space-between">
          <Text fontSize="lg" fontWeight="bold" color={colors.text}>
            📊 Chart Visualization
          </Text>
          <Badge colorScheme="blue" variant="subtle">
            {chartData.chart_type.toUpperCase()}
          </Badge>
        </HStack>
        
        <Box
          borderRadius="md"
          overflow="hidden"
          border="1px solid"
          borderColor={colors.cardBorder}
        >
          <img
            src={`data:image/png;base64,${chartData.image_base64}`}
            alt={`${chartData.chart_type} chart`}
            style={{
              width: '100%',
              height: 'auto',
              maxHeight: '500px',
              objectFit: 'contain'
            }}
          />
        </Box>
        
        {chartData.data && chartData.data.length > 0 && (
          <Box>
            <Text fontSize="sm" fontWeight="medium" color={colors.text} mb={2}>
              Data Summary ({chartData.row_count} rows):
            </Text>
            <Box
              maxH="200px"
              overflowY="auto"
              bg={colors.inputBg}
              borderRadius="md"
              p={3}
              fontSize="xs"
              fontFamily="mono"
            >
              <Text color={colors.text + '80'}>
                Columns: {chartData.columns.join(', ')}
              </Text>
              <Text color={colors.text + '80'} mt={1}>
                Chart Type: {chartData.chart_type}
              </Text>
              {chartData.x_column && (
                <Text color={colors.text + '80'}>
                  X-axis: {chartData.x_column}
                </Text>
              )}
              {chartData.y_column && (
                <Text color={colors.text + '80'}>
                  Y-axis: {chartData.y_column}
                </Text>
              )}
            </Box>
          </Box>
        )}
      </VStack>
    </Box>
  );
};

// Function to make URLs clickable in text content
const makeUrlsClickable = (text: string): string => {
  // Skip processing if the text already contains HTML tags (like citation links)
  if (text.includes('<a href=') || text.includes('<span class=')) {
    return text;
  }
  
  // Regex to match http:// or https:// URLs
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  
  let result = text.replace(urlRegex, (url) => {
    // Ensure the URL is properly encoded for HTML
    const encodedUrl = url.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return `<a href="${encodedUrl}" target="_blank" rel="noopener noreferrer" style="color: #3182ce; text-decoration: underline; font-weight: 500; transition: all 0.2s ease-in-out;" onmouseover="this.style.color='#2c5282'; this.style.textDecoration='none'; this.style.transform='translateY(-1px)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)' onmouseout="this.style.color='#3182ce'; this.style.textDecoration='underline'; this.style.transform='none'; this.style.boxShadow='none'">${url}</a>`;
  });
  
  // Convert file paths to clickable links (for local files)
  const filePathRegex = /(File:\s*)([^\s]+)/g;
  result = result.replace(filePathRegex, (_match, prefix, filePath) => {
    // Ensure the file path is properly encoded for HTML
    const encodedPath = filePath.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return `${prefix}<a href="file://${encodedPath}" target="_blank" rel="noopener noreferrer" style="color: #38a169; text-decoration: underline; font-weight: 500; transition: all 0.2s ease-in-out;" onmouseover="this.style.color='#2f855a'; this.style.textDecoration='none'; this.style.transform='translateY(-1px)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)'" onmouseout="this.style.color='#38a169'; this.style.textDecoration='underline'; this.style.transform='none'; this.style.boxShadow='none'">${filePath}</a>`;
  });
  
  return result;
};

// Function to extract project acronyms and node IDs from context data
const extractProjectAcronyms = (contextData: any): Array<{ acronym: string; nodeId: string; title?: string }> => {
  const acronyms: Array<{ acronym: string; nodeId: string; title?: string }> = [];
  
  if (!contextData) return acronyms;
  
  console.log('Extracting project acronyms from context data:', contextData);
  console.log('Context data keys:', Object.keys(contextData || {}));
  if (contextData.neo4j) {
    console.log('Neo4j data structure:', contextData.neo4j);
    if (Array.isArray(contextData.neo4j) && contextData.neo4j.length > 0) {
      console.log('First Neo4j item keys:', Object.keys(contextData.neo4j[0]));
      console.log('First Neo4j item:', contextData.neo4j[0]);
    }
  }
  
  // Extract from Neo4j results
  if (contextData.neo4j && Array.isArray(contextData.neo4j)) {
    contextData.neo4j.forEach((item: any) => {
      // Look for acronym and node ID fields
      Object.keys(item).forEach(key => {
        console.log(`Checking key: "${key}" with value: "${item[key]}"`);
        if (key.toLowerCase().includes('acronym') && item[key]) {
          const acronym = item[key];
          console.log(`Found acronym: "${acronym}"`);
          
          // Look for corresponding node ID
          let nodeId = '';
          let title = '';
          
          // Check for node.id field - handle both nested and flat structures
          if (item.node && item.node.id) {
            nodeId = item.node.id;
            console.log(`Found nodeId from item.node.id: "${nodeId}"`);
          } else if (item['node.id']) {
            nodeId = item['node.id'];
            console.log(`Found nodeId from item['node.id']: "${nodeId}"`);
          } else if (item.id) {
            nodeId = item.id;
            console.log(`Found nodeId from item.id: "${nodeId}"`);
          }
          
          // Check for title - handle both nested and flat structures
          if (item.title) {
            title = item.title;
            console.log(`Found title from item.title: "${title}"`);
          } else if (item['node.title']) {
            title = item['node.title'];
            console.log(`Found title from item['node.title']: "${title}"`);
          } else if (item.node && item.node.title) {
            title = item.node.title;
            console.log(`Found title from item.node.title: "${title}"`);
          }
          
          if (nodeId && !acronyms.find(a => a.acronym === acronym && a.nodeId === nodeId)) {
            acronyms.push({ acronym, nodeId, title });
            console.log(`Added acronym: "${acronym}" with nodeId: "${nodeId}"`);
          } else {
            console.log(`Skipped acronym: "${acronym}" - no nodeId or already exists`);
          }
        }
      });
    });
  }
  
  // Extract from Qdrant results
  if (contextData.qdrant && Array.isArray(contextData.qdrant)) {
    contextData.qdrant.forEach((item: any) => {
      Object.keys(item).forEach(key => {
        if (key.toLowerCase().includes('acronym') && item[key]) {
          const acronym = item[key];
          let nodeId = '';
          let title = '';
          
          if (item.id) {
            nodeId = item.id;
          }
          if (item.title) {
            title = item.title;
          }
          
          if (nodeId && !acronyms.find(a => a.acronym === acronym && a.nodeId === nodeId)) {
            acronyms.push({ acronym, nodeId, title });
          }
        }
      });
    });
  }
  
  // Extract from Elasticsearch results
  if (contextData.elasticsearch && Array.isArray(contextData.elasticsearch)) {
    contextData.elasticsearch.forEach((item: any) => {
      Object.keys(item).forEach(key => {
        if (key.toLowerCase().includes('acronym') && item[key]) {
          const acronym = item[key];
          let nodeId = '';
          let title = '';
          
          if (item.id) {
            nodeId = item.id;
          }
          if (item.title) {
            title = item.title;
          }
          
          if (nodeId && !acronyms.find(a => a.acronym === acronym && a.nodeId === nodeId)) {
            acronyms.push({ acronym, nodeId, title });
          }
        }
      });
    });
  }
  
  console.log('Extracted acronyms:', acronyms);
  return acronyms;
};

// Function to add node visualizer icons next to project acronyms
const addNodeVisualizerIcons = (content: string, projectAcronyms: Array<{ acronym: string; nodeId: string; title?: string }>): string => {
  console.log('Adding node visualizer icons for acronyms:', projectAcronyms);
  if (projectAcronyms.length === 0) return content;
  
  let processedContent = content;
  
  // Sort acronyms by length (longest first) to avoid partial matches
  const sortedAcronyms = [...projectAcronyms].sort((a, b) => b.acronym.length - a.acronym.length);
  
  sortedAcronyms.forEach(({ acronym, nodeId, title }) => {
    console.log(`Processing acronym: "${acronym}" with nodeId: "${nodeId}"`);
    
    // Create a regex that matches the acronym as a whole word, including when wrapped in HTML tags
    // This handles both plain text and <strong>acronym</strong> cases
    const escapedAcronym = acronym.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    
    // Only match markdown bold format **acronym** or <strong>acronym</strong> (after conversion)
    const patterns = [
      // Pattern 1: Markdown bold format **acronym**
      new RegExp(`\\*\\*${escapedAcronym}\\*\\*`, 'gi'),
      // Pattern 2: Wrapped in <strong> tags (after markdown conversion)
      new RegExp(`<strong>${escapedAcronym}</strong>`, 'gi')
    ];
    
    console.log(`Regex patterns:`, patterns.map(p => p.source));
    
    console.log(`Content to search: "${processedContent}"`);
    
    // Try each pattern and replace matches
    patterns.forEach((pattern, index) => {
      console.log(`Trying pattern ${index + 1}: ${pattern.source}`);
      
      // Test if the regex matches anything
      const matches = processedContent.match(pattern);
      console.log(`Found matches with pattern ${index + 1}:`, matches);
      
      if (matches && matches.length > 0) {
        // Replace each occurrence with the acronym + visualizer icon
        processedContent = processedContent.replace(pattern, (match) => {
          console.log(`Replacing match: "${match}"`);
          const tooltipText = title ? `${acronym}: ${title}` : acronym;
          
          // Check if the match is wrapped in <strong> tags
          if (match.startsWith('<strong>') && match.endsWith('</strong>')) {
            // Extract the acronym from the HTML tags
            const acronymText = match.replace(/<\/?strong>/g, '');
            return `<strong>${acronymText}</strong><span class="node-visualizer-icon" data-node-id="${nodeId}" data-acronym="${acronym}" title="${tooltipText}"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z"/><circle cx="12" cy="12" r="3"/></svg></span>`;
          } else if (match.startsWith('**') && match.endsWith('**')) {
            // Extract the acronym from the markdown tags
            const acronymText = match.replace(/\*\*/g, '');
            return `**${acronymText}**<span class="node-visualizer-icon" data-node-id="${nodeId}" data-acronym="${acronym}" title="${tooltipText}"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z"/><circle cx="12" cy="12" r="3"/></svg></span>`;
          } else {
            // This shouldn't happen now, but keep as fallback
            return `${match}<span class="node-visualizer-icon" data-node-id="${nodeId}" data-acronym="${acronym}" title="${tooltipText}"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z"/><circle cx="12" cy="12" r="3"/></svg></span>`;
          }
        });
      }
    });
  });
  
  return processedContent;
};

// Function to convert markdown bold syntax to HTML bold tags
const convertMarkdownBold = (text: string): string => {
  // Convert **text** to <strong>text</strong>
  return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
};

// Function to process message content with markdown formatting
const processMessageContent = (content: string, contextData?: any, isAssistantMessage: boolean = false): string => {
  console.log('processMessageContent - Original content:', content);
  console.log('processMessageContent - Context data:', contextData);
  console.log('processMessageContent - Is assistant message:', isAssistantMessage);
  
  // First convert markdown bold syntax to HTML
  let processedContent = convertMarkdownBold(content);
  console.log('processMessageContent - After markdown conversion:', processedContent);
  
  // Then add node visualizer icons next to project acronyms if context data is available AND it's an assistant message
  // Do this AFTER markdown conversion to work with <strong> tags
  if (contextData && isAssistantMessage) {
    const projectAcronyms = extractProjectAcronyms(contextData);
    console.log('processMessageContent - Extracted acronyms:', projectAcronyms);
    processedContent = addNodeVisualizerIcons(processedContent, projectAcronyms);
    console.log('processMessageContent - After adding icons:', processedContent);
  }
  
  // Then make URLs clickable
  processedContent = makeUrlsClickable(processedContent);
  
  return processedContent;
};

// Helper function to calculate context size in bytes/KB
const getContextSize = (contextData: any[] | null | undefined): string => {
  if (!contextData || !Array.isArray(contextData)) {
    return '0 B';
  }
  
  try {
    // Convert context data to JSON string to calculate size
    const jsonString = JSON.stringify(contextData);
    const sizeInBytes = new Blob([jsonString]).size;
    
    if (sizeInBytes < 1024) {
      return `${sizeInBytes} B`;
    } else {
      const sizeInKB = (sizeInBytes / 1024).toFixed(1);
      return `${sizeInKB} KB`;
    }
  } catch (error) {
    return '0 B';
  }
};

const getTotalContextLength = (contextData: any, totalContextSizeBytes?: number): string => {
  if (totalContextSizeBytes !== undefined) {
    // Use backend-provided context size (includes previous contexts if applicable)
    if (totalContextSizeBytes < 1024) {
      return `${totalContextSizeBytes} B`;
    } else {
      const sizeInKB = (totalContextSizeBytes / 1024).toFixed(1);
      return `${sizeInKB} KB`;
    }
  }
  
  // Fallback to local calculation if backend size not available
  if (!contextData) return '0 KB'
  
  try {
    // Convert context data to JSON string to calculate size
    const jsonString = JSON.stringify(contextData);
    const sizeInBytes = new Blob([jsonString]).size;
    
    if (sizeInBytes < 1024) {
      return `${sizeInBytes} B`;
    } else {
      const sizeInKB = (sizeInBytes / 1024).toFixed(1);
      return `${sizeInKB} KB`;
    }
  } catch (error) {
    return '0 KB';
  }
}

const extractConfidenceMetadata = (content: string): { confidence?: { level: 'high' | 'medium' | 'low', percentage: number }, cleanedContent: string } => {
  const confidenceMatch = content.match(/<!-- CONFIDENCE_METADATA: (high|medium|low):(\d+) -->/);
  
  if (confidenceMatch) {
    const level = confidenceMatch[1] as 'high' | 'medium' | 'low';
    const percentage = parseInt(confidenceMatch[2]);
    
    // Remove the metadata comment from the content
    const cleanedContent = content.replace(/<!-- CONFIDENCE_METADATA: (high|medium|low):(\d+) -->/, '').trim();
    
    return {
      confidence: { level, percentage },
      cleanedContent
    };
  }
  
  return { cleanedContent: content };
}

const parseJsonResponse = (content: string): { sentences: string[], confidence?: { level: 'high' | 'medium' | 'low', percentage: number } } => {
  try {
    // First, extract confidence metadata if present
    const confidenceExtracted = extractConfidenceMetadata(content);
    const contentWithoutConfidence = confidenceExtracted.cleanedContent;
    
    // Try to parse as JSON
    const jsonData = JSON.parse(contentWithoutConfidence);
    
    if (jsonData.sentences && Array.isArray(jsonData.sentences)) {
      // Extract sentences from the JSON structure
      const sentences = jsonData.sentences.map((item: any) => {
        if (typeof item === 'string') {
          return item;
        } else if (item.sentence) {
          return item.sentence;
        }
        return '';
      }).filter((sentence: string) => sentence.trim() !== '');
      
      return {
        sentences,
        confidence: confidenceExtracted.confidence
      };
    }
  } catch (error) {
    console.log('Not a JSON response, treating as plain text');
  }
  
  // If not JSON or no sentences found, return as plain text
  const confidenceExtracted = extractConfidenceMetadata(content);
  return {
    sentences: [confidenceExtracted.cleanedContent],
    confidence: confidenceExtracted.confidence
  };
}

const extractSentencesFromPartialJson = (content: string): { sentences: string[], isComplete: boolean, partialSentence?: string } => {
  try {
    // Try to extract sentences from partial JSON content
    // Look for sentence patterns in the JSON structure
    const sentenceMatches = content.match(/"sentence":\s*"([^"]*)"/g);
    
    if (sentenceMatches) {
      const sentences = sentenceMatches.map(match => {
        // Extract the sentence text from the match
        const sentenceMatch = match.match(/"sentence":\s*"([^"]*)"/);
        return sentenceMatch ? sentenceMatch[1] : '';
      }).filter(sentence => sentence.trim() !== '');
      
      // Check if the JSON appears to be complete
      const isComplete = content.trim().endsWith('}') || content.trim().endsWith(']');
      
      // Look for partial sentence (incomplete sentence being streamed)
      const partialSentenceMatch = content.match(/"sentence":\s*"([^"]*)$/);
      const partialSentence = partialSentenceMatch ? partialSentenceMatch[1] : undefined;
      
      return {
        sentences,
        isComplete,
        partialSentence
      };
    }
  } catch (error) {
    // If parsing fails, it might be incomplete JSON
  }
  
  return {
    sentences: [],
    isComplete: false
  };
}

const formatSentencesForDisplay = (sentences: string[]): string => {
  if (sentences.length === 0) return '';
  if (sentences.length === 1) return sentences[0];
  
  // Format multiple sentences as one paragraph
  return sentences.map((sentence) => {
    const trimmedSentence = sentence.trim();
    if (!trimmedSentence) return '';
    
    return trimmedSentence;
  }).filter(sentence => sentence.trim() !== '').join(' ');
}

// Function to strip HTML tags and get clean plain text
const stripHtmlTags = (html: string): string => {
  // Create a temporary DOM element to parse HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html;
  
  // Get text content (this automatically strips HTML tags)
  let text = tempDiv.textContent || tempDiv.innerText || '';
  
  // Clean up extra whitespace and normalize line breaks
  text = text
    .replace(/\s+/g, ' ') // Replace multiple spaces with single space
    .replace(/\n\s*\n/g, '\n\n') // Replace multiple line breaks with double line breaks
    .trim();
  
  return text;
};

// Function to copy response content and references to clipboard
const copyResponseToClipboard = async (message: Message, contextData: any, content: string): Promise<boolean> => {
  try {
    // Generate links from context data
    const generatedLinks = generateLinksFromContext(contextData, content);
    
    // Strip HTML tags from the message content to get clean plain text
    const cleanContent = stripHtmlTags(message.content);
    
    // Build the text to copy
    let textToCopy = cleanContent + '\n\n';
    
    if (generatedLinks.length > 0) {
      textToCopy += 'References:\n';
      generatedLinks.forEach((link, index) => {
        textToCopy += `${index + 1}. ${link.title}\n   ${link.url}\n\n`;
      });
    }
    
    // Copy to clipboard
    await navigator.clipboard.writeText(textToCopy);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
};



interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  id?: string // Optional ID for tracking messages
  contextUsed?: {
    neo4j: boolean
    neo4j_planner?: boolean
    qdrant: boolean
    elasticsearch: boolean
    ollama: boolean
  }
  contextData?: {
    neo4j: any[] | null
    neo4j_planner?: any[] | null
    qdrant: any[] | null
    elasticsearch: any[] | null
    ollama: any[] | null
  }
  contextSources?: {
    neo4j_planner?: {
      enabled: boolean
      data: any[]
      formatted: string
      toast_data?: any
    }
    qdrant?: {
      enabled: boolean
      data: any[]
      formatted: string
    }
    elasticsearch?: {
      enabled: boolean
      data: any[]
      formatted: string
    }
  }
  chartData?: {
    chart_type: string
    image_base64: string
    data: any[]
    columns: string[]
    row_count: number
    x_column?: string
    y_column?: string
    labels_column?: string
    values_column?: string
    value_column?: string
    pivot_data?: any
  }
  elapsedTime?: number
  previousContextsIncluded?: boolean
  totalContextSizeBytes?: number
  confidence?: {
    level: 'high' | 'medium' | 'low'
    percentage: number
  }
  tokenCounts?: {
    user_question: number
    planner_prompt: number
    planner_output: number
    context: number
    prev_context: number
    chat_history: number
    system_instructions: number
    final_llm_output: number
    total: number
  }
  lucene_query?: string
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  titleSet: boolean; // Track if title has been set after first question
  createdAt?: string; // Creation timestamp
  updatedAt?: string; // Last update timestamp
  lastMessageAt?: string | null; // Last message timestamp
  messageCount?: number; // Number of messages in the session
  isNew?: boolean; // Flag to identify newly created sessions
}
export const Chat = () => {
  const colors = useThemeColors();
  const { currentUser, loading: authLoading } = useAuth();
  
  // Add CSS for blinking animation
  useEffect(() => {
    // Add the blink animation CSS if it doesn't exist
    if (!document.getElementById('blink-animation-style')) {
      const style = document.createElement('style');
      style.id = 'blink-animation-style';
      style.textContent = `
        @keyframes blink {
          0% { opacity: 0.3; }
          50% { opacity: 1; }
          100% { opacity: 0.3; }
        }
        
        .node-visualizer-icon {
          display: inline-block;
          margin-left: 4px;
          cursor: pointer;
          color: #ff8c00;
          font-size: 14px;
          animation: blink 3s ease-in-out infinite;
          transition: all 0.2s ease;
        }
        
        .node-visualizer-icon:hover {
          color: #ffa500;
          transform: scale(1.2);
          animation: none;
        }
        
        /* Dark theme colors */
        [data-theme="dark"] .node-visualizer-icon {
          color: #ffd700;
        }
        
        [data-theme="dark"] .node-visualizer-icon:hover {
          color: #ffed4e;
        }
      `;
      document.head.appendChild(style);
    }
  }, []);
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isHovering, setIsHovering] = useState(false)
  const [selectedModel, setSelectedModel] = useState('openai-gpt4o-mini')
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState<string | null>(null)
  const [editedTitle, setEditedTitle] = useState('')

  const [abortController, setAbortController] = useState<AbortController | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)
  const [progressStage, setProgressStage] = useState<'idle' | 'llm1' | 'data_retrieval' | 'llm2'>('idle')
  // Previous context is always set to 'smart' - removed user control
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const toast = useToast()

  // Function to create a new chat session
    const createNewSession = async () => {
    try {
      const response = await apiPost('/chat/sessions')
      
      if (!response.ok) {
        throw new Error('Failed to create new session')
      }
      
      const newSession = await response.json()
      
      // Ensure the new session has the current timestamp to appear at the top
      const currentTime = new Date().toISOString()
      const sessionData = {
        id: newSession.session_id,
        title: newSession.title,
        messages: [],
        titleSet: newSession.title_set,
        createdAt: currentTime, // Use current time to ensure it appears at top
        updatedAt: currentTime,
        lastMessageAt: undefined,
        messageCount: 0,
        isNew: true // Flag to identify newly created sessions
      }
      
      // Add the new session to the top of the list immediately
      setChatSessions(prev => [sessionData, ...prev])
      setCurrentSessionId(newSession.session_id)
      setMessages([])
      
      // Remove the isNew flag when the user sends their first message
      // This will happen in handleSendMessage when the session gets updated
    } catch (error) {
      console.error('Error creating new session:', error)
      toast({
        title: "Error",
        description: "Failed to create new chat session.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Function to handle chat selection
  const handleSelectChat = async (sessionId: string) => {
    setCurrentSessionId(sessionId)
    
    try {
      const response = await apiGet(`/chat/${sessionId}/messages`)
      if (response.ok) {
        const messagesData = await response.json()
        console.log('Raw messages data from database:', messagesData);
        
        const formattedMessages: Message[] = messagesData.map((msg: any) => {
          console.log('Processing message:', msg);
          console.log('Message context_used:', msg.context_used);
          console.log('Message context_data:', msg.context_data);
          
          // Parse context_data if it's a JSON string
          let parsedContextData = msg.context_data;
          if (typeof msg.context_data === 'string') {
            try {
              parsedContextData = JSON.parse(msg.context_data);
            } catch (e) {
              console.error('Failed to parse context_data JSON:', e);
              parsedContextData = null;
            }
          }
          
          // Filter context data to remove only truly internal fields (like _planner_prompt)
          if (parsedContextData && typeof parsedContextData === 'object') {
            const filterInternalFields = (obj: any): any => {
              if (Array.isArray(obj)) {
                return obj.map(item => filterInternalFields(item));
              } else if (obj && typeof obj === 'object') {
                const filtered: any = {};
                for (const [key, value] of Object.entries(obj)) {
                  // Keep essential fields that start with _ but are needed for toast display
                  const essentialInternalFields = [
                    '_query_type', '_cleaned_query', '_plan', '_cypher', '_function', 
                    '_is_backup', '_message', '_raw_planner_output', '_prev_context_needed'
                  ];
                  
                  // Only filter out truly internal fields like _planner_prompt
                  if (!key.startsWith('_') || essentialInternalFields.includes(key)) {
                    filtered[key] = filterInternalFields(value);
                  }
                }
                return filtered;
              }
              return obj;
            };
            
            parsedContextData = filterInternalFields(parsedContextData);
          }
          
          // Format Neo4j context data for toast display (similar to backend format_neo4j_context_toast)
          const formatNeo4jContextForToast = (neo4jData: any[]): any => {
            if (!neo4jData || neo4jData.length === 0) {
              return {
                planner_llm_output: "No Neo4j results found.",
                generated_cyphers: "No Cypher queries generated.",
                execution_results: "No execution results available."
              };
            }
            
            try {
              const firstResult = neo4jData[0];
              const queryType = firstResult._query_type || firstResult.query_type || 'unknown';
              
              if (queryType === 'planner_generated' || queryType === 'planner_backup') {
                const plan = firstResult._plan || firstResult.plan || [];
                const cleanedQuery = firstResult._cleaned_query || firstResult.cleaned_query || 'Unknown query';
                const isBackup = firstResult._is_backup || firstResult.is_backup || false;
                const message = firstResult._message || firstResult.message || 'No message';
                
                // 1. Planner LLM Output (JSON format)
                const rawPlannerOutput = firstResult._raw_planner_output || firstResult.raw_planner_output || {};
                let plannerOutput: any = {};
                
                if (rawPlannerOutput.complete_planner_response) {
                  const completeResponse: any = rawPlannerOutput.complete_planner_response;
                  // Filter out internal fields
                  for (const [key, value] of Object.entries(completeResponse)) {
                    if (!key.startsWith('_')) {
                      plannerOutput[key] = value;
                    }
                  }
                  
                  // Add essential fields if missing
                  if (!plannerOutput.original_query) plannerOutput.original_query = cleanedQuery;
                  if (!plannerOutput.cleaned_query) plannerOutput.cleaned_query = cleanedQuery;
                  if (!plannerOutput.is_backup) plannerOutput.is_backup = isBackup;
                  if (!plannerOutput.message) plannerOutput.message = message;
                  if (!plannerOutput.plan) plannerOutput.plan = plan;
                  if (!plannerOutput.plan_steps_count) plannerOutput.plan_steps_count = plan.length;
                } else {
                  plannerOutput = {
                    original_query: cleanedQuery,
                    cleaned_query: cleanedQuery,
                    is_backup: isBackup,
                    message: message,
                    plan: plan,
                    plan_steps_count: plan.length
                  };
                }
                
                // 2. Generated Cyphers
                const generatedCyphers: any = {};
                if (isBackup) {
                  const backupCypher = rawPlannerOutput.backup_cypher || firstResult._cypher || firstResult.cypher || 'Unknown query';
                  generatedCyphers.backup_cypher = {
                    function: "BACKUP_CYPHER",
                    cypher_query: backupCypher
                  };
                } else {
                  // Group by function
                  for (const result of neo4jData) {
                    if (result._cypher && result._function) {
                      generatedCyphers[result._function] = {
                        function: result._function,
                        cypher_query: result._cypher
                      };
                    }
                  }
                }
                
                // 3. Execution Results
                const executionResults = [];
                for (const result of neo4jData) {
                  if (result._message) continue; // Skip metadata-only results
                  
                  const cleanResult: any = {};
                  for (const [key, value] of Object.entries(result)) {
                    if (!key.startsWith('_')) {
                      cleanResult[key] = value;
                    }
                  }
                  
                  if (Object.keys(cleanResult).length > 0) {
                    executionResults.push(cleanResult);
                  }
                }
                
                return {
                  planner_llm_output: plannerOutput,
                  generated_cyphers: generatedCyphers,
                  execution_results: executionResults,
                  total_results: executionResults.length,
                  query_type: queryType
                };
              } else {
                // Legacy LLM results
                return {
                  planner_llm_output: "Legacy LLM results - no planner data available",
                  generated_cyphers: "Legacy LLM results - no Cypher queries available",
                  execution_results: neo4jData,
                  total_results: neo4jData.length,
                  query_type: queryType
                };
              }
            } catch (error) {
              console.error('Error formatting Neo4j context for toast:', error);
              return {
                planner_llm_output: "Error formatting Neo4j data",
                generated_cyphers: "Error formatting Cypher queries",
                execution_results: "Error formatting execution results"
              };
            }
          };
          
          // Prepare context sources - use stored ones if they have proper structure, otherwise regenerate
          let contextSources;
          if (msg.context_sources) {
            // Check if the stored context_sources has proper toast_data structure
            const hasProperToastData = msg.context_sources?.neo4j_planner?.toast_data && 
              typeof msg.context_sources.neo4j_planner.toast_data === 'object' &&
              msg.context_sources.neo4j_planner.toast_data.planner_llm_output &&
              msg.context_sources.neo4j_planner.toast_data.generated_cyphers &&
              msg.context_sources.neo4j_planner.toast_data.execution_results;
            
            if (hasProperToastData) {
              // Use stored context_sources if it has proper toast_data structure
              contextSources = msg.context_sources;
            } else if (parsedContextData) {
              // Regenerate context_sources with proper toast_data if stored data is incomplete
              contextSources = {
                neo4j_planner: parsedContextData.neo4j_planner ? {
                  enabled: true,
                  data: parsedContextData.neo4j_planner,
                  formatted: "Neo4j data loaded from database",
                  toast_data: formatNeo4jContextForToast(parsedContextData.neo4j_planner)
                } : undefined,
                qdrant: parsedContextData.qdrant ? {
                  enabled: true,
                  data: parsedContextData.qdrant,
                  formatted: "Qdrant data loaded from database"
                } : undefined,
                elasticsearch: parsedContextData.elasticsearch ? {
                  enabled: true,
                  data: parsedContextData.elasticsearch,
                  formatted: "Elasticsearch data loaded from database"
                } : undefined
              };
            }
          } else if (parsedContextData) {
            contextSources = {
              neo4j_planner: parsedContextData.neo4j_planner ? {
                enabled: true,
                data: parsedContextData.neo4j_planner,
                formatted: "Neo4j data loaded from database",
                toast_data: formatNeo4jContextForToast(parsedContextData.neo4j_planner)
              } : undefined,
              qdrant: parsedContextData.qdrant ? {
                enabled: true,
                data: parsedContextData.qdrant,
                formatted: "Qdrant data loaded from database"
              } : undefined,
              elasticsearch: parsedContextData.elasticsearch ? {
                enabled: true,
                data: parsedContextData.elasticsearch,
                formatted: "Elasticsearch data loaded from database"
              } : undefined
            };
          }
          
          // Parse JSON content if it's a JSON response
          let parsedContent = msg.content;
          if (msg.role === 'assistant' && typeof msg.content === 'string' && msg.content.trim().startsWith('{')) {
            try {
              const parsed = parseJsonResponse(msg.content);
              parsedContent = formatSentencesForDisplay(parsed.sentences);
              console.log('Parsed JSON content for loaded message:', {
                original: msg.content.substring(0, 100) + '...',
                parsed: parsedContent
              });
            } catch (error) {
              console.error('Failed to parse JSON content for loaded message:', error);
              // Keep original content if parsing fails
              parsedContent = msg.content;
            }
          }

          
          const formattedMessage: Message = {
            id: msg.id, // Include the message ID from database
            role: msg.role,
            content: parsedContent,
            timestamp: msg.timestamp,
            contextUsed: msg.context_used ? {
              neo4j: msg.context_used.includes('neo4j_planner') || msg.context_used.includes('neo4j_llm') || msg.context_used.includes('neo4j'),
              qdrant: msg.context_used.includes('qdrant'),
              elasticsearch: msg.context_used.includes('elasticsearch'),
              ollama: false
            } : undefined,
            contextData: parsedContextData ? {
              neo4j: parsedContextData.neo4j_planner || parsedContextData.neo4j_llm || parsedContextData.neo4j || null,
              qdrant: parsedContextData.qdrant || null,
              elasticsearch: parsedContextData.elasticsearch || null,
              ollama: null
            } : undefined,
            contextSources: contextSources,
            elapsedTime: msg.elapsed_time,
            confidence: msg.confidence, // Include confidence data from database
            tokenCounts: msg.token_counts, // Include token counts from database
            lucene_query: msg.lucene_query, // Include lucene_query from database
            previousContextsIncluded: false // This field is not stored in database, only available in current response
          };
          
          // Debug context data
          console.log('Message context_data from DB:', msg.context_data);
          console.log('Message lucene_query from DB:', msg.lucene_query);
          console.log('Formatted message contextData:', formattedMessage.contextData);
          console.log('Formatted message lucene_query:', formattedMessage.lucene_query);
          
          console.log('Formatted message:', formattedMessage);
          return formattedMessage;
        });
        
        // Clean up orphaned messages (user messages without corresponding assistant responses)
        const cleanedMessages = formattedMessages.filter((msg, index) => {
          if (msg.role === 'user') {
            // Check if there's a following assistant message
            const hasFollowingAssistant = index < formattedMessages.length - 1 && 
                                        formattedMessages[index + 1]?.role === 'assistant'
            return hasFollowingAssistant
          }
          return true // Keep all assistant messages
        })
        
        setMessages(cleanedMessages)
      } else {
        console.error('Failed to load messages')
        setMessages([])
      }
    } catch (error) {
      console.error('Error loading messages:', error)
      setMessages([])
    }
  }

  // Function to update chat title
  const updateChatTitle = async (sessionId: string, newTitle: string) => {
    try {
      const response = await apiPut(`/chat/${sessionId}/title`, { title: newTitle })
      
      if (response.ok) {
        const updatedSession = await response.json()
        setChatSessions(prev => prev.map(session => 
          session.id === sessionId ? { 
            ...session, 
            title: updatedSession.title, 
            titleSet: updatedSession.title_set 
          } : session
        ))
      } else {
        throw new Error('Failed to update title')
      }
    } catch (error) {
      console.error('Error updating title:', error)
      toast({
        title: "Error",
        description: "Failed to update chat title.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Function to handle title edit start
  const handleStartEdit = (sessionId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingTitle(sessionId)
    setEditedTitle(currentTitle)
  }

  // Function to handle title save
  const handleSaveTitle = async (sessionId: string, e: React.FormEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (editedTitle.trim()) {
      await updateChatTitle(sessionId, editedTitle.trim())
    }
    setEditingTitle(null)
  }

  // Handle sending message
  const handleSendMessage = async () => {
    if (!input.trim()) return

    const userMessageId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const newMessage: Message = {
      id: userMessageId, // Add unique ID for tracking
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    // Update both local messages and session messages
    setMessages(prev => [...prev, newMessage])
    setChatSessions(prev => prev.map(session => 
      session.id === currentSessionId 
        ? { ...session, messages: [...session.messages, newMessage] }
        : session
    ))
    setInput('')
    setIsLoading(true)
    setIsStreaming(true)
    setProgressStage('llm1')

    try {
      const controller = new AbortController()
      setAbortController(controller)

      // Log the selected model for debugging
      console.log('Sending message with model:', selectedModel)

      // Simulate progress stages with timeouts
      setTimeout(() => setProgressStage('data_retrieval'), 3000)
      setTimeout(() => setProgressStage('llm2'), 6000)

      // Create initial AI message for streaming
      const aiMessageId = `ai_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      const aiMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        id: aiMessageId // Add unique ID for tracking
      }

      // Add the AI message to the chat immediately
      setMessages(prev => [...prev, aiMessage])

      let fullResponse = ''

      console.log('Starting streaming request...')

      // Use streaming API
      await apiStream(
        '/chat/stream',
        {
          message: input,
          session_id: currentSessionId,
          model: selectedModel,
        },
        (chunk) => {
          console.log('Received chunk:', chunk)
          if (chunk.type === 'chunk') {
            fullResponse += chunk.content
            console.log('Updated response:', fullResponse)
            
            // Check if this looks like JSON response (legacy support)
            const isJsonResponse = fullResponse.trim().startsWith('{') && !fullResponse.includes('<div class="formatted-content">');
            
            let displayContent = '';
            let confidence = undefined;
            let partialExtracted: any = null;
            
            if (isJsonResponse) {
              // Try to extract sentences from partial JSON (legacy support)
              partialExtracted = extractSentencesFromPartialJson(fullResponse)
              
              if (partialExtracted.sentences.length > 0 || partialExtracted.partialSentence) {
                // We found sentences or a partial sentence in the JSON
                const allSentences = [...partialExtracted.sentences];
                
                // Add partial sentence if it exists
                if (partialExtracted.partialSentence) {
                  allSentences.push(partialExtracted.partialSentence);
                }
                
                displayContent = formatSentencesForDisplay(allSentences)
                console.log('Using partial JSON extraction (legacy):', {
                  sentencesCount: partialExtracted.sentences.length,
                  hasPartialSentence: !!partialExtracted.partialSentence,
                  partialSentence: partialExtracted.partialSentence,
                  isComplete: partialExtracted.isComplete
                })
              } else {
                // No sentences extracted yet, show the raw chunk content for word-by-word effect
                displayContent = chunk.content
                console.log('Showing raw chunk content for word-by-word streaming (legacy JSON)')
              }
            } else {
              // Not JSON or already formatted HTML, show the raw chunk content for word-by-word effect
              displayContent = chunk.content
              console.log('Non-JSON response or formatted HTML, showing raw chunk content')
            }
            
            // Try to extract confidence from the full response
            const confidenceExtracted = extractConfidenceMetadata(fullResponse)
            confidence = confidenceExtracted.confidence
            
            console.log('Response parsing:', {
              isJson: isJsonResponse,
              sentencesCount: partialExtracted?.sentences.length || 0,
              hasPartialSentence: !!partialExtracted?.partialSentence,
              hasConfidence: !!confidence,
              confidence: confidence,
              contentLength: fullResponse.length,
              displayContentLength: displayContent.length
            })
            
            // Update the AI message content in real-time using ID
            setMessages(prev => {
              console.log('Updating messages - Current messages:', prev.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
              console.log('Looking for AI message with ID:', aiMessageId);
              
              const updated = prev.map(msg => {
                if (msg.id === aiMessageId) {
                  console.log('Found AI message to update:', { id: msg.id, role: msg.role, oldContentLength: msg.content.length, newContentLength: displayContent.length });
                  return { 
                    ...msg, 
                    content: displayContent,
                    confidence: confidence
                  };
                }
                return msg;
              });
              
              console.log('Updated messages:', updated.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
              return updated;
            })
          } else if (chunk.type === 'error') {
            console.error('Streaming error chunk:', chunk)
            // Handle error
            setMessages(prev => {
              console.log('Error updating messages - Current messages:', prev.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
              console.log('Looking for AI message with ID:', aiMessageId);
              
              const updated = prev.map(msg => {
                if (msg.id === aiMessageId) {
                  console.log('Found AI message to update with error:', { id: msg.id, role: msg.role });
                  return { ...msg, content: chunk.content };
                }
                return msg;
              });
              
              console.log('Error updated messages:', updated.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
              return updated;
            })
          }
        },
        async (metadata?: any) => {
          console.log('Stream ended successfully with metadata:', metadata)
          // Stream ended
          setIsLoading(false)
          setIsStreaming(false)
          setProgressStage('idle')
          setAbortController(null)
          
          console.log('Final message before update:', {
            aiMessageId,
            currentMessages: messages.filter(msg => msg.id === aiMessageId),
            hasConfidence: messages.find(msg => msg.id === aiMessageId)?.confidence
          })
          
          // Parse the final response to get clean content
          const finalParsed = parseJsonResponse(fullResponse)
          const finalDisplayContent = formatSentencesForDisplay(finalParsed.sentences)
          
          // Update the final message with metadata and replace temporary IDs with database IDs
          setMessages(prev => {
            console.log('Final update - Current messages:', prev.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
            console.log('Looking for AI message with ID:', aiMessageId);
            console.log('Message IDs from metadata:', metadata?.message_ids);
            
            const updated = prev.map(msg => {
              // Replace temporary IDs with database IDs if available
              let newId = msg.id;
              if (msg.role === 'user' && metadata?.message_ids?.user_message_id) {
                newId = metadata.message_ids.user_message_id;
                console.log('Replacing user message ID:', { old: msg.id, new: newId });
              } else if (msg.role === 'assistant' && msg.id === aiMessageId && metadata?.message_ids?.assistant_message_id) {
                newId = metadata.message_ids.assistant_message_id;
                console.log('Replacing assistant message ID:', { old: msg.id, new: newId });
              }
              
              if (msg.id === aiMessageId) {
                console.log('Found AI message for final update:', { id: msg.id, role: msg.role, oldContentLength: msg.content.length, newContentLength: finalDisplayContent.length });
                return { 
                  ...msg, 
                  id: newId, // Use the new database ID
                  content: finalDisplayContent,
                  contextUsed: metadata?.context_used ? {
                    neo4j: metadata.context_used.neo4j_planner || false,
                    qdrant: metadata.context_used.qdrant || false,
                    elasticsearch: metadata.context_used.elasticsearch || false,
                    ollama: false
                  } : undefined,
                  contextData: metadata?.context_data ? {
                    neo4j: metadata.context_data.neo4j_planner || metadata.context_data.neo4j || null,
                    qdrant: metadata.context_data.qdrant || null,
                    elasticsearch: metadata.context_data.elasticsearch || null,
                    ollama: null
                  } : undefined,
                  contextSources: metadata?.context_sources || undefined,
                  elapsedTime: metadata?.elapsed_time,
                  previousContextsIncluded: metadata?.previous_contexts_included || false,
                  totalContextSizeBytes: metadata?.total_context_size_bytes,
                  confidence: metadata?.confidence || finalParsed.confidence || msg.confidence, // Use backend confidence if available, otherwise keep extracted confidence
                  tokenCounts: metadata?.token_counts || undefined,
                  lucene_query: metadata?.lucene_query || undefined
                };
              } else if (msg.role === 'user' && metadata?.message_ids?.user_message_id) {
                // Also update user message ID if it's the last user message
                return { ...msg, id: newId };
              }
              return msg;
            });
            
            console.log('Final updated messages:', updated.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length })));
            return updated;
          })
          
          console.log('Final message after update:', {
            aiMessageId,
            updatedMessages: messages.filter(msg => msg.id === aiMessageId),
            hasConfidence: messages.find(msg => msg.id === aiMessageId)?.confidence,
            confidenceData: metadata?.confidence
          })
          
          // Refresh chat sessions to get updated titles
          try {
            const sessionsResponse = await apiGet('/chat/sessions')
            if (sessionsResponse.ok) {
              const sessionsData = await sessionsResponse.json()
              const sessions = sessionsData.map((session: any) => ({
                id: session.id,
                title: session.title,
                messages: [],
                titleSet: session.title_set,
                createdAt: session.created_at,
                updatedAt: session.updated_at,
                lastMessageAt: session.last_message_at,
                messageCount: session.message_count,
                isNew: false
              }))
              setChatSessions(sessions)
              console.log('Refreshed chat sessions after streaming:', sessions)
            }
          } catch (error) {
            console.error('Error refreshing chat sessions after streaming:', error)
          }
        },
        (error) => {
          console.error('Streaming error:', error)
          // Try fallback to regular chat endpoint
          console.log('Trying fallback to regular chat endpoint...')
          
          // Remove the empty AI message
          setMessages(prev => prev.filter(msg => msg.id !== aiMessageId))
          
          // Use regular chat endpoint as fallback
          apiPost('/chat', {
            message: input,
            session_id: currentSessionId,
            model: selectedModel,
          }).then(async (response) => {
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`)
            }
            
            const data = await response.json()
            
            // Use confidence data from response, fallback to extracting from content
            let confidence = data.confidence;
            let content = data.response;
            
            // If confidence is not in response, try to extract from content
            if (!confidence) {
              const extracted = extractConfidenceMetadata(data.response);
              confidence = extracted.confidence;
              content = extracted.cleanedContent;
            }
            
            const aiMessage: Message = {
              id: data.message_ids?.assistant_message_id || `ai_fallback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`, // Use database ID if available, otherwise fallback ID
              role: 'assistant',
              content: content,
              contextUsed: {
                neo4j: data.context_used?.neo4j_planner || data.context_used?.neo4j_llm || data.context_used?.neo4j || false,
                qdrant: data.context_used?.qdrant || false,
                elasticsearch: data.context_used?.elasticsearch || false,
                ollama: false
              },
              contextData: {
                neo4j: data.context_data?.neo4j_planner || data.context_data?.neo4j_llm || data.context_data?.neo4j || null,
                qdrant: data.context_data?.qdrant || null,
                elasticsearch: data.context_data?.elasticsearch || null,
                ollama: null
              },
              contextSources: data.context_sources || undefined,
              chartData: data.chart_data || undefined,
              elapsedTime: data.elapsed_time,
              previousContextsIncluded: data.previous_contexts_included || false,
              totalContextSizeBytes: data.total_context_size_bytes,
              confidence: confidence,
              tokenCounts: data.token_counts || undefined,
              lucene_query: data.lucene_query || undefined,
              timestamp: new Date().toISOString()
            }
            
            // Update both user and assistant message IDs with database IDs if available
            setMessages(prev => {
              const updated = prev.map(msg => {
                // Update user message ID if it's the last user message and we have the database ID
                if (msg.role === 'user' && msg.id === userMessageId && data.message_ids?.user_message_id) {
                  return { ...msg, id: data.message_ids.user_message_id };
                }
                return msg;
              });
              return [...updated, aiMessage];
            });
            
            setIsLoading(false)
            setIsStreaming(false)
            setProgressStage('idle')
            setAbortController(null)
            
          }).catch((fallbackError) => {
            console.error('Fallback also failed:', fallbackError)
            setIsLoading(false)
            setIsStreaming(false)
            setProgressStage('idle')
            setAbortController(null)
            
            toast({
              title: "Error",
              description: "Failed to get response from the AI.",
              status: "error",
              duration: 5000,
              isClosable: true,
              position: "top-right",
            })
          })
        }
      )

    } catch (error) {
      console.error('Error in handleSendMessage:', error)
      setIsLoading(false)
      setIsStreaming(false)
      setProgressStage('idle')
      setAbortController(null)
      
      toast({
        title: "Error",
        description: "Failed to send message.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Initialize chat sessions from database
  useEffect(() => {
    const initializeSessions = async () => {
      console.log('Chat: initializeSessions called', { isInitialized, currentUser: !!currentUser, authLoading });
      
      if (!isInitialized && currentUser && !authLoading) {
        console.log('Chat: Starting to initialize sessions');
        try {
          // Get chat sessions with timestamps from database (with shorter timeout for initial load)
          const response = await apiGet('/chat/sessions', 15000) // 15 second timeout
          if (response.ok) {
            const sessionsData = await response.json()
            const sessions = sessionsData.map((session: any) => ({
              id: session.id,
              title: session.title,
              messages: [],
              titleSet: session.title_set,
              createdAt: session.created_at,
              updatedAt: session.updated_at,
              lastMessageAt: session.last_message_at,
              messageCount: session.message_count
            }))
            
            if (sessions.length > 0) {
              setChatSessions(sessions)
              setCurrentSessionId(sessions[0].id)
              // Load messages for the first session (with timeout)
              try {
                await handleSelectChat(sessions[0].id)
              } catch (error) {
                console.error('Error loading first session messages:', error)
                // Continue with empty messages if loading fails
              }
            } else {
              // Create a new session if none exist
              await createNewSession()
            }
          } else {
            console.warn('Failed to fetch sessions, creating new session')
            // Create a new session if API fails
            await createNewSession()
          }
        } catch (error) {
          console.error('Error initializing sessions:', error)
          // Create a new session if initialization fails
          try {
            await createNewSession()
          } catch (createError) {
            console.error('Failed to create new session:', createError)
            // Show error to user
            toast({
              title: "Initialization Error",
              description: "Failed to initialize chat. Please refresh the page.",
              status: "error",
              duration: 5000,
              isClosable: true,
            })
          }
        }
        setIsInitialized(true)
      }
    }
    
    initializeSessions()
  }, [isInitialized, currentUser, authLoading]) // Run when user is authenticated

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Enhanced scroll function with delay to ensure content is rendered
  const scrollToBottomWithDelay = () => {
    // Immediate scroll
    scrollToBottom()
    
    // Additional scroll after a short delay to ensure content is fully rendered
    setTimeout(() => {
      scrollToBottom()
    }, 100)
    
    // Another scroll after a longer delay for very long content
    setTimeout(() => {
      scrollToBottom()
    }, 500)
  }

  // Auto-scroll when messages change
  useEffect(() => {
    if (messages.length > 0) {
      // Check if the last message is from assistant (new response)
      const lastMessage = messages[messages.length - 1]
      if (lastMessage.role === 'assistant') {
        scrollToBottomWithDelay()
      } else {
        scrollToBottom()
      }
    }
  }, [messages])

  // Auto-scroll when a new chat is created
  useEffect(() => {
    if (chatSessions.length > 0) {
      scrollToBottom()
    }
  }, [chatSessions.length])

  // Auto-scroll when current session changes
  useEffect(() => {
    if (currentSessionId) {
      scrollToBottom()
    }
  }, [currentSessionId])



  // Add click event listener for node visualizer icons using event delegation
  useEffect(() => {
    const handleIconClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const iconElement = target.closest('.node-visualizer-icon');
      
      if (iconElement) {
        const nodeId = iconElement.getAttribute('data-node-id');
        const acronym = iconElement.getAttribute('data-acronym');
        
        if (nodeId && acronym) {
          console.log('Icon clicked via event delegation:', { nodeId, acronym });
          handleNodeVisualizerClick(nodeId, acronym);
        }
      }
    };

    // Add event listener to the document
    document.addEventListener('click', handleIconClick);
    
    return () => {
      document.removeEventListener('click', handleIconClick);
    };
  }, []);

  // Auto-scroll when loading completes (response is ready)
  useEffect(() => {
    if (!isLoading && messages.length > 0) {
      const lastMessage = messages[messages.length - 1]
      if (lastMessage.role === 'assistant') {
        // Add a small delay to ensure the response content is fully rendered
        setTimeout(() => {
          scrollToBottomWithDelay()
        }, 200)
      }
    }
  }, [isLoading, messages])

  const handleHeatmapClick = async (luceneQuery: string) => {
    console.log('handleHeatmapClick called with lucene_query:', luceneQuery);
    
    setHeatmapLoading(true);
    
    try {
      // Import the API function
      const { postHeatmapWithLucene } = await import('../utils/api');
      
      const response = await postHeatmapWithLucene(luceneQuery, heatmapMetric);
      
      if (response.ok && response.data.length > 0) {
        console.log('Heatmap response data:', response.data);
        // Set the heatmap data and show the modal
        setHeatmapData(response.data);
        setHeatmapLuceneQuery(luceneQuery);
        setHeatmapMetric(response.metric);
        setShowHeatmapModal(true);
        
        toast({
          title: "Heatmap Generated",
          description: `Generated heatmap for ${response.data.length} countries. Opening visualization...`,
          status: "success",
          duration: 2000,
          isClosable: true,
          position: "top-right",
        });
      } else {
        toast({
          title: "No Heatmap Data",
          description: "No geographic data found for your query.",
          status: "info",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        });
      }
    } catch (error) {
      console.error('Heatmap error:', error);
      toast({
        title: "Error",
        description: "Failed to generate heatmap. Please try again.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      });
    } finally {
      setHeatmapLoading(false);
    }
  }

  const handlePartnerFinderClick = async (luceneQuery: string) => {
    console.log('handlePartnerFinderClick called with lucene_query:', luceneQuery);
    
    setPartnerFinderLoading(true);
    
    try {
      // Import the API function
      const { postFindPartnersWithLucene } = await import('../utils/api');
      
      const response = await postFindPartnersWithLucene(luceneQuery);
      
      if (response.ok && response.partners.length > 0) {
        // Set the partner results and show the modal
        setPartnerResults(response.partners);
        setPartnerResultsLuceneQuery(luceneQuery);
        setPartnerResultsOriginalQuery((response as any).original_query || '');
        setPartnerResultsExpandedQuery((response as any).expanded_query || '');
        setShowPartnerResultsModal(true);
        
        toast({
          title: "Partners Found",
          description: `Found ${response.partners.length} similar organizations. Opening results...`,
          status: "success",
          duration: 2000,
          isClosable: true,
          position: "top-right",
        });
      } else {
        toast({
          title: "No Partners Found",
          description: "No similar organizations found for your query.",
          status: "info",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        });
      }
    } catch (error) {
      console.error('Partner finder error:', error);
      toast({
        title: "Error",
        description: "Failed to find partners. Please try again.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      });
    } finally {
      setPartnerFinderLoading(false);
    }
  }

  const handleCoParticipationClick = async (luceneQuery: string) => {
    console.log('handleCoParticipationClick called with lucene_query:', luceneQuery);
    
    setCoParticipationLoading(true);
    
    try {
      // Import the API function
      const { postCoParticipationWithLucene } = await import('../utils/api');
      
      const response = await postCoParticipationWithLucene(luceneQuery);
      
      if (response.ok && response.url) {
        // Open the visualization in a new tab
        const fullUrl = response.url.startsWith('http') ? response.url : `/api${response.url}`;
        window.open(fullUrl, "_blank", "noopener,noreferrer");
        
        toast({
          title: "Co-participation Visualization",
          description: "Opening co-participation network visualization in a new tab.",
          status: "success",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        });
      } else {
        toast({
          title: "No Visualization Created",
          description: "No co-participation network could be created for your query.",
          status: "info",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        });
      }
    } catch (error) {
      console.error('Co-participation error:', error);
      toast({
        title: "Error",
        description: "Failed to create co-participation visualization. Please try again.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      });
    } finally {
      setCoParticipationLoading(false);
    }
  }

  const handleContextClick = (contextType: string, contextData: any[] | null | undefined, contextSources?: any) => {
    console.log('handleContextClick called:', { contextType, contextData, contextSources });
    
    if (!contextData && contextType !== 'neo4j') {
      console.log('No context data available');
      toast({
        title: "No Context Data",
        description: "No context data is available for this response.",
        status: "info",
        duration: 3000,
        isClosable: true,
        position: "top-right",
      });
      return;
    }
     
    // For Neo4j, we want to show the planner output even if there are no results
    if (contextType === 'neo4j' && (!contextData || contextData.length === 0)) {
      console.log('Neo4j context with no results - showing planner info');
      toast({
        title: "Neo4j Planner",
        description: "Planner LLM was used but no results were found. Check the plan and generated Cypher query.",
        status: "info",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      });
      return;
    }
    
    if (contextType === 'neo4j' && contextSources?.neo4j_planner?.toast_data) {
      // Use the new toast data format for Neo4j
      const toastData = contextSources.neo4j_planner.toast_data;
      
      // Show the complete Neo4j context information
      toast({
        title: "Neo4j Context - Complete Information",
        description: (
          <Box maxH="600px" overflowY="auto">
            <VStack align="start" spacing={4}>
              {/* Planner LLM Output */}
              <Box w="100%">
                <Text fontWeight="bold" color={colors.primary} mb={2}>
                  🔍 Planner LLM Output (JSON)
                </Text>
                <Box 
                  bg={colors.bg}
                  p={3}
                  borderRadius="md"
                  border="1px solid"
                  borderColor={colors.border}
                  maxH="200px"
                  overflowY="auto"
                >
                  <Text 
                    fontFamily="monospace" 
                    fontSize="xs"
                    whiteSpace="pre-wrap"
                    color={colors.text}
                  >
                    {JSON.stringify(toastData.planner_llm_output, null, 2)}
                  </Text>
                </Box>
              </Box>
              
              {/* Generated Cyphers */}
              <Box w="100%">
                <Text fontWeight="bold" color={colors.primary} mb={2}>
                  🔧 Generated Cypher Queries
                </Text>
                <Box 
                  bg={colors.bg}
                  p={3}
                  borderRadius="md"
                  border="1px solid"
                  borderColor={colors.border}
                  maxH="200px"
                  overflowY="auto"
                >
                  <Text 
                    fontFamily="monospace" 
                    fontSize="xs"
                    whiteSpace="pre-wrap"
                    color={colors.text}
                  >
                    {JSON.stringify(toastData.generated_cyphers, null, 2)}
                  </Text>
                </Box>
              </Box>
              
              {/* Execution Results */}
              <Box w="100%">
                <Text fontWeight="bold" color={colors.primary} mb={2}>
                  📊 Cypher Execution Results ({toastData.total_results} total)
                </Text>
                <Box 
                  bg={colors.bg}
                  p={3}
                  borderRadius="md"
                  border="1px solid"
                  borderColor={colors.border}
                  maxH="300px"
                  overflowY="auto"
                >
                  <Text 
                    fontFamily="monospace" 
                    fontSize="xs"
                    whiteSpace="pre-wrap"
                    color={colors.text}
                  >
                    {JSON.stringify(toastData.execution_results, null, 2)}
                  </Text>
                </Box>
              </Box>
            </VStack>
          </Box>
        ),
        status: "info",
        duration: 15000,
        isClosable: true,
        position: "top-right",
      });
      return;
    }
    
    let contextText = '';
    if (contextType === 'ollama') {
      // Handle keywords display
      contextText = Array.isArray(contextData) ? contextData.join('\n') : '';
    } else if (contextType === 'neo4j' && contextData) {
      // Use the formatted content from context sources if available
      if (contextSources && contextSources.neo4j_planner && contextSources.neo4j_planner.formatted) {
        contextText = contextSources.neo4j_planner.formatted;
      } else {
        // Fallback to legacy handling if context sources not available
        const firstItem = contextData[0];
        
        if (firstItem && firstItem._query_type === 'planner_generated') {
          // Handle Planner LLM output
          const plan = firstItem._plan || [];
          const cleanedQuery = firstItem._cleaned_query || 'Unknown query';
          const message = firstItem._message || 'No message';
          
          let planText = '';
          if (plan.length > 0) {
            planText = plan.map((step: any, index: number) => {
              return `Step ${index + 1}: ${step.name}\nParameters: ${JSON.stringify(step.parameters, null, 2)}`;
            }).join('\n\n');
          }
          
          contextText = `=== PLANNER LLM OUTPUT ===\n\nCleaned Query: ${cleanedQuery}\n\nPlan:\n${planText}\n\nMessage: ${message}\n\n=== QUERY RESULTS ===\n${JSON.stringify(contextData, null, 2)}`;
        } else {
          // Handle legacy Neo4j data as raw JSON with Cypher query
          const cypherQuery = firstItem?._cypher_query || 'Unknown query';
          
          // Create a clean version of the data without _cypher_query, _query_type, and _vector
          const cleanData = contextData.map(item => {
            const { _cypher_query, _query_type, _vector, ...cleanItem } = item;
            return cleanItem;
          });
          
          const jsonData = JSON.stringify(cleanData, null, 2);
          // Replace escaped newlines with actual newlines
          const formattedJsonData = jsonData.replace(/\\n/g, '\n');
          const formattedCypherQuery = cypherQuery.replace(/\\n/g, '\n');
          contextText = `Neo4j Results (JSON):\n${formattedJsonData}\n\nCypher Query Used:\n${formattedCypherQuery}`;
        }
      }
    } else if (contextType === 'elasticsearch' && contextData) {
      // Handle Elasticsearch data
      contextText = contextData.map((item, index) => {
        if (!item.content) {
          return null;
        }
        const highlights = item.highlights ? Object.entries(item.highlights).map(([field, values]) => 
          `${field}: ${Array.isArray(values) ? values.join('...') : values}`
        ).join('\n') : '';
        
        return `Document ${index + 1}:\nContent: ${item.content}\nFilename: ${item.filename || 'Unknown'}\nIndex: ${item.index || 'Unknown'}\nScore: ${item.score.toFixed(2)}\n${highlights ? `Highlights:\n${highlights}\n` : ''}`;
      })
      .filter(Boolean)
      .join('\n\n');
    } else if (contextData) {
      // Handle Qdrant data
      contextText = contextData.map((item, index) => {
        if (!item.content) {
          return null;
        }
        return `Document ${index + 1}:\nContent: ${item.content}\n${item.source ? `Source: ${item.source}\n` : ''}Relevance Score: ${item.score.toFixed(2)}\nCollection: ${item.collection || 'Unknown'}`;
      })
      .filter(Boolean)
      .join('\n\n');
    }
    
    if (!contextText.trim()) {
      console.log('No context text available');
      toast({
        title: "No Content Available",
        description: "No relevant content found for this context.",
        status: "info",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      });
      return;
    }
    
    console.log('Showing toast for context:', contextType);
    console.log('Context text length:', contextText.length);
    
    // Try a simple toast first to test if the system works
    toast({
      title: `${contextType === 'ollama' ? 'Extracted Keywords' : contextType.charAt(0).toUpperCase() + contextType.slice(1) + ' Context'}`,
      description: `Context data available: ${contextData ? contextData.length : 0} items`,
      status: "info",
      duration: 5000,
      isClosable: true,
      position: "top-right",
    });
    
    // Then show the detailed toast
    setTimeout(() => {
      toast({
        title: `${contextType === 'ollama' ? 'Extracted Keywords' : contextType.charAt(0).toUpperCase() + contextType.slice(1) + ' Context'}`,
        description: (
          <Box 
            maxH="400px" 
            overflowY="auto" 
            whiteSpace="pre-wrap"
            className="prose prose-sm"
            sx={{
              'p': { marginBottom: '1em', textAlign: 'left' },
              'ul': { marginBottom: '1em', paddingLeft: '1.5em', textAlign: 'left' },
              'ol': { marginBottom: '1em', paddingLeft: '1.5em', textAlign: 'left' },
              'li': { marginBottom: '0.5em', textAlign: 'left' },
              'h1, h2, h3, h4': { 
                marginTop: '1em', 
                marginBottom: '0.5em', 
                fontWeight: 'bold',
                textAlign: 'left'
              },
              'code': { 
                backgroundColor: 'gray.200',
                padding: '0.2em 0.4em',
                borderRadius: '0.25em',
                fontSize: '0.875em'
              },
              'pre': {
                backgroundColor: 'gray.200',
                padding: '1em',
                borderRadius: '0.5em',
                overflowX: 'auto',
                marginBottom: '1em',
                textAlign: 'left'
              }
            }}
          >
            {contextType === 'ollama' ? (
              <VStack align="start" spacing={2}>
                <Text fontWeight="bold">Extracted Keywords:</Text>
                <UnorderedList>
                  {Array.isArray(contextData) && contextData.map((keyword, index) => (
                    <ListItem key={index}>{keyword}</ListItem>
                  ))}
                </UnorderedList>
              </VStack>
            ) : contextType === 'neo4j' ? (
              <Box>
                <Text 
                  whiteSpace="pre-wrap" 
                  fontFamily="monospace" 
                  fontSize="xs"
                  bg={colors.bg}
                  color={colors.text}
                  p={2}
                  borderRadius="md"
                  border="1px solid"
                  borderColor={colors.border}
                  maxH="400px"
                  overflowY="auto"
                >
                  {contextText}
                </Text>
              </Box>
            ) : contextType === 'qdrant' ? (
              <Box>
                <VStack align="start" spacing={3} maxH="400px" overflowY="auto">
                  {contextData?.map((item, index) => {
                    if (!item.content) return null;
                    
                    return (
                      <Box 
                        key={index}
                        w="100%"
                        p={3}
                        bg={colors.bg}
                        borderRadius="md"
                        border="1px solid"
                        borderColor={colors.border}
                      >
                        <Text 
                          fontWeight="bold" 
                          fontSize="sm"
                          color={colors.primary}
                          mb={2}
                        >
                          Document {index + 1}
                        </Text>
                        <VStack align="start" spacing={1} fontSize="xs">
                          <Text color={colors.text}>
                            <strong>Content:</strong> {item.content.substring(0, 500)}...
                          </Text>
                          {item.source && (
                            <Text color={colors.text}>
                              <strong>Source:</strong> {item.source}
                            </Text>
                          )}
                          <Text color={colors.text}>
                            <strong>Relevance Score:</strong> {item.score.toFixed(2)}
                          </Text>
                          <Text color={colors.text}>
                            <strong>Collection:</strong> {item.collection || 'Unknown'}
                          </Text>
                        </VStack>
                      </Box>
                    );
                  })}
                </VStack>
              </Box>
            ) : (
              contextText
            )}
          </Box>
        ),
        status: "info",
        duration: 10000,
        isClosable: true,
        position: "top-right",
      });
    }, 100);
  };

  const handleStopRequest = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setIsLoading(false);
      setIsHovering(false);
      setProgressStage('idle');
      
      // Add a message indicating the request was stopped
      const errorMessage: Message = {
        id: `ai_error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`, // Add unique ID for tracking
        role: 'assistant',
        content: 'Request was stopped by the user.',
        timestamp: new Date().toISOString(),
        contextUsed: {
          neo4j: false,
          qdrant: false,
          elasticsearch: false,
          ollama: false
        },
        contextData: {
          neo4j: null,
          qdrant: null,
          elasticsearch: null,
          ollama: null
        }
      }
      setMessages(prev => [...prev, errorMessage])
    }
  };

  // Add function to remove chat
  const handleRemoveChat = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent triggering the chat selection
    console.log('Removing chat session:', sessionId, 'Current sessions:', chatSessions.length)
    
    try {
      const response = await apiDelete(`/chat/${sessionId}`)
      
      if (response.ok) {
        setChatSessions(prev => {
          const updatedSessions = prev.filter(session => session.id !== sessionId)
          console.log('After removal, sessions count:', updatedSessions.length)
          
          // If we're removing the current chat, handle the selection
          if (currentSessionId === sessionId) {
            if (updatedSessions.length > 0) {
              // Select the first available chat
              const firstSession = updatedSessions[0]
              console.log('Selecting first available session:', firstSession.id)
              setCurrentSessionId(firstSession.id)
              setMessages(firstSession.messages)
            } else {
              // Create a new chat if none remain
              console.log('No sessions remaining, creating new one')
              createNewSession()
            }
          }
          
          return updatedSessions
        })
      } else {
        throw new Error('Failed to delete session')
      }
    } catch (error) {
      console.error('Error removing chat:', error)
      toast({
        title: "Error",
        description: "Failed to remove chat session.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Add function to delete individual message pair
  const handleDeleteMessage = async (messageIndex: number, e: React.MouseEvent) => {
    e.stopPropagation()
    
    // Find the message pair (user message + assistant response)
    const userMessageIndex = messageIndex - 1
    const assistantMessageIndex = messageIndex
    
    // Check if we have a valid message pair
    if (userMessageIndex < 0 || assistantMessageIndex >= messages.length) {
      toast({
        title: "Error",
        description: "Cannot delete incomplete message pair.",
        status: "error",
        duration: 3000,
        isClosable: true,
        position: "top-right",
      })
      return
    }
    
    const userMessage = messages[userMessageIndex]
    const assistantMessage = messages[assistantMessageIndex]
    
    if (userMessage.role !== 'user' || assistantMessage.role !== 'assistant') {
      toast({
        title: "Error",
        description: "Invalid message pair structure.",
        status: "error",
        duration: 3000,
        isClosable: true,
        position: "top-right",
      })
      return
    }
    
    try {
      // Delete both messages from the database with better error handling
      const deleteResults = []
      
      // Delete user message
      if (userMessage.id) {
        try {
          const userResponse = await apiDelete(`/chat/message/${userMessage.id}`)
          deleteResults.push({ message: 'user', success: userResponse.ok, response: userResponse })
        } catch (error) {
          console.error('Error deleting user message:', error)
          deleteResults.push({ message: 'user', success: false, error })
        }
      } else {
        console.warn('User message has no ID, skipping database deletion')
        deleteResults.push({ message: 'user', success: true, response: null })
      }
      
      // Delete assistant message
      if (assistantMessage.id) {
        try {
          const assistantResponse = await apiDelete(`/chat/message/${assistantMessage.id}`)
          deleteResults.push({ message: 'assistant', success: assistantResponse.ok, response: assistantResponse })
        } catch (error) {
          console.error('Error deleting assistant message:', error)
          deleteResults.push({ message: 'assistant', success: false, error })
        }
      } else {
        console.warn('Assistant message has no ID, skipping database deletion')
        deleteResults.push({ message: 'assistant', success: true, response: null })
      }
      
      // Check results and handle partial failures
      const actualDeletions = deleteResults.filter(result => result.response !== null) // Only count actual database deletions
      const successfulDeletions = actualDeletions.filter(result => result.success)
      const failedDeletions = actualDeletions.filter(result => !result.success)
      const skippedDeletions = deleteResults.filter(result => result.response === null) // Messages without IDs that were skipped
      
      // Debug logging
      console.log('Deletion results:', {
        deleteResults,
        actualDeletions,
        successfulDeletions,
        failedDeletions,
        skippedDeletions,
        userMessageId: userMessage.id,
        assistantMessageId: assistantMessage.id
      })
      
      // Always remove from local state since we want to remove the message pair from UI
      setMessages(prev => {
        const updatedMessages = [...prev]
        updatedMessages.splice(userMessageIndex, 2) // Remove both messages
        return updatedMessages
      })
      
      // Determine the appropriate message based on what actually happened
      if (actualDeletions.length === 0) {
        // No actual database deletions occurred (both messages had no IDs)
        toast({
          title: "Success",
          description: "Message pair removed from chat.",
          status: "success",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        })
      } else if (failedDeletions.length === 0) {
        // All actual deletions were successful
        toast({
          title: "Success",
          description: "Message pair deleted successfully.",
          status: "success",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        })
      } else {
        // Some actual deletions failed
        console.warn('Partial deletion success:', { 
          successful: successfulDeletions, 
          failed: failedDeletions, 
          skipped: skippedDeletions 
        })
        toast({
          title: "Partial Success",
          description: "Some messages were deleted. You may need to refresh to see the complete result.",
          status: "warning",
          duration: 5000,
          isClosable: true,
          position: "top-right",
        })
      }
    } catch (error) {
      console.error('Error deleting message pair:', error)
      toast({
        title: "Error",
        description: "Failed to delete message pair.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Function to delete orphaned messages (user messages without corresponding assistant responses)
  const handleDeleteOrphanedMessage = async (messageIndex: number, e: React.MouseEvent) => {
    e.stopPropagation()
    
    const message = messages[messageIndex]
    
    if (message.role !== 'user') {
      toast({
        title: "Error",
        description: "Can only delete user messages.",
        status: "error",
        duration: 3000,
        isClosable: true,
        position: "top-right",
      })
      return
    }
    
    // Check if this is actually an orphaned message (no following assistant message)
    if (messageIndex < messages.length - 1 && messages[messageIndex + 1]?.role === 'assistant') {
      toast({
        title: "Error",
        description: "This message has a corresponding response. Use the delete button on the response instead.",
        status: "error",
        duration: 3000,
        isClosable: true,
        position: "top-right",
      })
      return
    }
    
    try {
      if (message.id) {
        const response = await apiDelete(`/chat/message/${message.id}`)
        
        if (response.ok) {
          // Remove the message from local state
          setMessages(prev => {
            const updatedMessages = [...prev]
            updatedMessages.splice(messageIndex, 1) // Remove only this message
            return updatedMessages
          })
          
          toast({
            title: "Success",
            description: "Orphaned message deleted successfully.",
            status: "success",
            duration: 3000,
            isClosable: true,
            position: "top-right",
          })
        } else {
          throw new Error('Failed to delete message from database')
        }
      } else {
        // Message has no ID, just remove from local state
        setMessages(prev => {
          const updatedMessages = [...prev]
          updatedMessages.splice(messageIndex, 1)
          return updatedMessages
        })
        
        toast({
          title: "Success",
          description: "Message removed from chat.",
          status: "success",
          duration: 3000,
          isClosable: true,
          position: "top-right",
        })
      }
    } catch (error) {
      console.error('Error deleting orphaned message:', error)
      toast({
        title: "Error",
        description: "Failed to delete orphaned message.",
        status: "error",
        duration: 5000,
        isClosable: true,
        position: "top-right",
      })
    }
  }

  // Poll system health every 60 seconds
  useEffect(() => {
    const pollHealth = async () => {
      console.log('Chat: Polling health');
      try {
        const response = await apiGet('/health_system');
        if (response.ok) {
          const data = await response.json();
          
          // Update chat titles from database (only for titles that haven't been manually set)
          if (data.chat_titles) {
            setChatSessions(prevSessions => {
              const updatedSessions = [...prevSessions];
              Object.entries(data.chat_titles).forEach(([sessionId, title]) => {
                const index = updatedSessions.findIndex(session => session.id === sessionId);
                if (index !== -1 && updatedSessions[index].title !== title && !updatedSessions[index].titleSet) {
                  updatedSessions[index] = {
                    ...updatedSessions[index],
                    title: title as string,
                    titleSet: true
                  };
                }
              });
              return updatedSessions;
            });
          }
        }
      } catch (error) {
        console.error('Error polling system health:', error);
      }
    };

    console.log('Chat: Health polling effect', { currentUser: !!currentUser, authLoading });
    if (currentUser && !authLoading) {
      console.log('Chat: Starting health polling');
      const interval = setInterval(pollHealth, 60000);
      return () => clearInterval(interval);
    }
  }, [currentUser, authLoading]);

  // Show loading state while authentication is being checked
  if (authLoading) {
    return (
      <Box h="100vh" display="flex" alignItems="center" justifyContent="center">
        <Text>Loading...</Text>
      </Box>
    );
  }

  // Mobile navigation state
  const { isOpen: isLeftDrawerOpen, onOpen: onLeftDrawerOpen, onClose: onLeftDrawerClose } = useDisclosure();
  const { isOpen: isRightDrawerOpen, onOpen: onRightDrawerOpen, onClose: onRightDrawerClose } = useDisclosure();
  
  // Partner results modal state
  const [partnerResults, setPartnerResults] = useState<any[]>([]);
  const [showPartnerResultsModal, setShowPartnerResultsModal] = useState(false);
  const [partnerResultsLuceneQuery, setPartnerResultsLuceneQuery] = useState<string>('');
  const [partnerResultsOriginalQuery, setPartnerResultsOriginalQuery] = useState<string>('');
  const [partnerResultsExpandedQuery, setPartnerResultsExpandedQuery] = useState<string>('');
  
  // Heatmap modal state
  const [heatmapData, setHeatmapData] = useState<any[]>([]);
  const [showHeatmapModal, setShowHeatmapModal] = useState(false);
  const [heatmapLuceneQuery, setHeatmapLuceneQuery] = useState<string>('');
  const [heatmapMetric, setHeatmapMetric] = useState<string>('projects');
  
  // Loading states for icons
  const [coParticipationLoading, setCoParticipationLoading] = useState(false);
  const [partnerFinderLoading, setPartnerFinderLoading] = useState(false);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  
  // Responsive values
  const navbarHeight = useBreakpointValue({ base: '56px', md: '64px' });
  const leftSidebarWidth = useBreakpointValue({ base: '100%', lg: '250px' });
  const rightSidebarWidth = useBreakpointValue({ base: '100%', lg: '280px' });

  // Function to handle node visualizer icon clicks
  const handleNodeVisualizerClick = (nodeId: string, acronym: string) => {
    console.log('Node visualizer clicked:', { nodeId, acronym });
    
    // Dispatch a custom event to fill the Node Visualizer input
    const fillEvent = new CustomEvent('fillNodeVisualizer', {
      detail: { nodeId, acronym }
    });
    console.log('Dispatching fillNodeVisualizer event:', fillEvent);
    
    // Try dispatching on both window and document
    window.dispatchEvent(fillEvent);
    document.dispatchEvent(fillEvent);
    console.log('Event dispatched successfully on both window and document');
    
    // Show a toast notification
    toast({
      title: "Node ID Filled",
      description: `Node ID "${nodeId}" has been filled in the Node Visualizer. Click "Visualize" to proceed.`,
      status: "info",
      duration: 3000,
      isClosable: true,
      position: "top-right",
    });
  };

  return (
    <Box h="100vh" overflow="hidden" bg={colors.bg}>
      <Navbar selectedModel={selectedModel} onModelChange={setSelectedModel} />
      
      {/* Desktop Right Sidebar - AI Model & System Health */}
      <Box
        position="fixed"
        top={{ base: navbarHeight, lg: "80px" }}
        right={0}
        width={rightSidebarWidth}
        zIndex={10}
        display={{ base: 'none', lg: 'block' }}
      >
        <Box
          w={rightSidebarWidth}
          borderLeft="1px"
          borderColor={colors.sidebarBorder}
          p={{ base: 4, lg: 6 }}
          display="flex"
          flexDirection="column"
          h={{ base: `calc(100vh - ${navbarHeight} - 20px)`, lg: "calc(100vh - 100px)" }}
          bg={colors.sidebarBg}
          borderRadius="xl"
          boxShadow={colors.shadowLg}
          backdropFilter="blur(10px)"
          overflowY="auto"
        >
          <VStack spacing={4} align="stretch">
            <Box>
              <SystemHealthComponent />
            </Box>
            <Box>
              <NodeVisualizer />
            </Box>
            <Box>
              <CoParticipationBox />
            </Box>
            <Box>
              <PartnerFinderBox />
            </Box>
          </VStack>
        </Box>
      </Box>

      {/* Main Layout */}
      <Flex pt={navbarHeight} height={`calc(100vh - ${navbarHeight})`} overflow="hidden">
        
        {/* Desktop Left Sidebar - Chat History */}
        <Box
          position="fixed"
          top={{ base: navbarHeight, lg: "80px" }}
          left={0}
          width={leftSidebarWidth}
          zIndex={5}
          display={{ base: 'none', lg: 'block' }}
        >
          <Box
            w={leftSidebarWidth}
            borderRight="1px"
            borderColor={colors.sidebarBorder}
            p={{ base: 4, lg: 6 }}
            display="flex"
            flexDirection="column"
            h={{ base: `calc(100vh - ${navbarHeight} - 20px)`, lg: "calc(100vh - 100px)" }}
            bg={colors.sidebarBg}
            borderRadius="xl"
            boxShadow={colors.shadowLg}
            backdropFilter="blur(10px)"
            overflowY="auto"
          >
            <VStack spacing={4} align="stretch">
              <Box>
                <Flex justify="space-between" align="center" mb={4}>
                  <Text 
                    fontSize="md" 
                    fontWeight="bold" 
                    color={colors.text}
                    textTransform="uppercase"
                    letterSpacing="wide"
                  >
                    Chat Sessions
                  </Text>
                  <IconButton
                    aria-label="New chat"
                    icon={<FiPlus />}
                    size="md"
                    onClick={createNewSession}
                    bg={colors.primary}
                    color="white"
                    borderRadius="lg"
                    w="40px"
                    h="40px"
                    _hover={{ 
                      bg: colors.primaryHover,
                      transform: 'translateY(-2px)',
                      boxShadow: colors.shadowLg,
                    }}
                    transition="all 0.2s ease-in-out"
                  />
                </Flex>
            <VStack 
              spacing={2} 
              align="stretch" 
              overflowY="auto" 
              flex="1" 
              pr={1}
              css={{
                '&::-webkit-scrollbar': {
                  width: '4px',
                },
                '&::-webkit-scrollbar-track': {
                  background: 'transparent',
                },
                '&::-webkit-scrollbar-thumb': {
                  background: colors.text + '20',
                  borderRadius: '4px',
                },
                '&::-webkit-scrollbar-thumb:hover': {
                  background: colors.text + '40',
                },
              }}
            >
              {chatSessions
                .sort((a, b) => {
                  // First priority: new sessions (force to top)
                  if ((a as any).isNew && !(b as any).isNew) return -1;
                  if (!(a as any).isNew && (b as any).isNew) return 1;
                  
                  // Sort by last message time, then by updated time, then by creation time (newest first)
                  const aLastMessageTime = a.lastMessageAt ? new Date(a.lastMessageAt).getTime() : 0;
                  const bLastMessageTime = b.lastMessageAt ? new Date(b.lastMessageAt).getTime() : 0;
                  
                  const aUpdatedTime = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
                  const bUpdatedTime = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
                  
                  const aCreatedTime = a.createdAt ? new Date(a.createdAt).getTime() : 0;
                  const bCreatedTime = b.createdAt ? new Date(b.createdAt).getTime() : 0;
                  
                  // Second priority: last message time (most recent activity)
                  if (aLastMessageTime !== bLastMessageTime) {
                    return bLastMessageTime - aLastMessageTime;
                  }
                  
                  // Third priority: updated time
                  if (aUpdatedTime !== bUpdatedTime) {
                    return bUpdatedTime - aUpdatedTime;
                  }
                  
                  // Fourth priority: creation time (newest first)
                  if (aCreatedTime !== bCreatedTime) {
                    return bCreatedTime - aCreatedTime;
                  }
                  
                  // Fallback: sort by session ID (newer IDs first)
                  return b.id.localeCompare(a.id);
                })
                .map(session => (
                <Box
                  key={session.id}
                  position="relative"
                  _hover={{ 
                    bg: colors.hoverBg,
                    transform: 'translateX(2px)',
                  }}
                  cursor="pointer"
                  onClick={() => handleSelectChat(session.id)}
                  bg={currentSessionId === session.id ? colors.activeBg : 'transparent'}
                  p={2}
                  borderRadius="lg"
                  border="1px solid"
                  borderColor={currentSessionId === session.id ? colors.primary : 'transparent'}
                  transition="all 0.2s ease-in-out"
                  boxShadow={currentSessionId === session.id ? colors.shadow : 'none'}
                  minH="auto"
                >
                  <VStack align="start" spacing={1} width="100%">
                    {editingTitle === session.id ? (
                      <form onSubmit={(e) => handleSaveTitle(session.id, e)} style={{ width: '100%' }}>
                        <Input
                          value={editedTitle}
                          onChange={(e) => setEditedTitle(e.target.value)}
                          size="xs"
                          autoFocus
                          onBlur={() => setEditingTitle(null)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            if (e.key === 'Escape') {
                              setEditingTitle(null)
                            }
                          }}
                          bg={colors.inputBg}
                          borderColor={colors.inputBorder}
                          color={colors.text}
                          _placeholder={{ color: colors.text + '60' }}
                          borderRadius="md"
                          fontSize="xs"
                        />
                      </form>
                    ) : (
                      <Flex align="center" justify="space-between" width="100%">
                        <VStack align="start" spacing={0} flex={1} minW={0}>
                          <Text
                            fontSize="xs"
                            fontWeight="medium"
                            noOfLines={2}
                            color={colors.text}
                            lineHeight="1.2"
                          >
                            {session.title}
                          </Text>
                          <Text fontSize="xs" color={colors.text + '60'} lineHeight="1.1">
                            {session.lastMessageAt 
                              ? new Date(session.lastMessageAt).toLocaleDateString() 
                              : (session.createdAt ? new Date(session.createdAt).toLocaleDateString() : 'No messages')}
                          </Text>
                        </VStack>
                        <HStack spacing={1} ml={2} flexShrink={0}>
                          <IconButton
                            aria-label="Edit title"
                            icon={<FiEdit2 size={12} />}
                            size="xs"
                            variant="ghost"
                            color={colors.text + '80'}
                            _hover={{ 
                              color: colors.primary,
                              bg: colors.hoverBg,
                            }}
                            onClick={(e) => handleStartEdit(session.id, session.title, e)}
                            minW="auto"
                            h="auto"
                            p={1}
                          />
                          <IconButton
                            aria-label="Remove chat"
                            icon={<FiX size={12} />}
                            size="xs"
                            variant="ghost"
                            onClick={(e) => handleRemoveChat(session.id, e)}
                            color={colors.text + '80'}
                            _hover={{ 
                              color: colors.error,
                              bg: colors.error + '20',
                            }}
                            minW="auto"
                            h="auto"
                            p={1}
                          />
                        </HStack>
                      </Flex>
                    )}
                  </VStack>
                </Box>
              ))}
            </VStack>
              </Box>
            </VStack>
          </Box>
        </Box>

        {/* Mobile Navigation Buttons */}
        <Flex 
          position="fixed" 
          top={{ base: navbarHeight, lg: "80px" }} 
          left="10px" 
          zIndex={15}
          display={{ base: 'flex', lg: 'none' }}
          gap={2}
        >
          <IconButton
            aria-label="Open chat history"
            icon={<FiMenu />}
            onClick={onLeftDrawerOpen}
            size="sm"
            bg={colors.sidebarBg}
            color={colors.text}
            border="1px solid"
            borderColor={colors.sidebarBorder}
            borderRadius="lg"
            boxShadow={colors.shadow}
            _hover={{
              bg: colors.hoverBg,
              transform: 'translateY(-1px)',
            }}
          />
          <IconButton
            aria-label="Open system tools"
            icon={<FiCpu />}
            onClick={onRightDrawerOpen}
            size="sm"
            bg={colors.sidebarBg}
            color={colors.text}
            border="1px solid"
            borderColor={colors.sidebarBorder}
            borderRadius="lg"
            boxShadow={colors.shadow}
            _hover={{
              bg: colors.hoverBg,
              transform: 'translateY(-1px)',
            }}
          />
        </Flex>

        {/* Main Chat Area */}
        <Box
          flex="1"
          display="flex"
          flexDirection="column"
          h="100%"
          ml={{ base: 0, lg: leftSidebarWidth }}
          mr={{ base: 0, lg: rightSidebarWidth }}
          width={{ base: "100%", lg: "calc(100% - 530px)" }}
          maxW={{ base: "100%", lg: "calc(100% - 530px)" }}
          minW={{ base: "100%", lg: "800px" }}
          px={{ base: 2, sm: 4, md: 6, lg: 8 }}
          bg={colors.bg}
        >
          {/* Messages Area - Takes up most of the space */}
          <Box
            overflowY="auto"
            p={{ base: 2, sm: 4, md: 6, lg: 8 }}
            display="flex"
            flexDirection="column"
            gap={{ base: 3, md: 6 }}
            minW="100%"
            bg={colors.cardBg}
            borderRadius="2xl"
            border="1px solid"
            borderColor={colors.cardBorder}
            boxShadow={colors.shadow}
            mb={[3, 4, 5]}
            mt={[3, 4, 5]}
            h={["calc(100vh - 240px)", "calc(105vh - 300px)"]}
          >
            {messages.length === 0 ? (
              // Empty state with MAPIT logo
              <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                h="100%"
                minH="400px"
                w="100%"
              >
                <Box
                  position="relative"
                  display="flex"
                  flexDirection="column"
                  alignItems="center"
                  justifyContent="center"
                  minH="300px"
                  w="100%"
                >
                  <Image
                    src={mapitLogo}
                    alt="MAPIT AI"
                    w={{ base: "140px", md: "210px", lg: "280px" }}
                    h="auto"
                    opacity={0.1}
                    position="absolute"
                    top="50%"
                    left="50%"
                    transform="translate(-50%, -50%)"
                    zIndex={0}
                    pointerEvents="none"
                    animation="pulse 4s ease-in-out infinite"
                    sx={{
                      '@keyframes pulse': {
                        '0%, 100%': { opacity: 0.1 },
                        '50%': { opacity: 0.15 }
                      }
                    }}
                  />
                  <VStack 
                    spacing={4} 
                    position="relative"
                    zIndex={1}
                    animation="fadeIn 2s ease-in-out"
                    sx={{
                      '@keyframes fadeIn': {
                        '0%': { opacity: 0, transform: 'translateY(20px)' },
                        '100%': { opacity: 1, transform: 'translateY(0)' }
                      }
                    }}
                  >
                    <Text
                      fontSize={{ base: "lg", md: "xl" }}
                      fontWeight="semibold"
                      color={colors.text}
                      opacity={0.7}
                      textAlign="center"
                      bg={colors.cardBg}
                      px={4}
                      py={2}
                      borderRadius="md"
                    >
                      Welcome to MAPIT AI
                    </Text>
                    <Text
                      fontSize={{ base: "sm", md: "md" }}
                      color={colors.text}
                      opacity={0.5}
                      textAlign="center"
                      maxW="400px"
                      bg={colors.cardBg}
                      px={4}
                      py={2}
                      borderRadius="md"
                    >
                      Start a conversation to explore research projects, organizations, and collaborations
                    </Text>
                  </VStack>
                </Box>
              </Box>
            ) : (
              messages.map((message, index) => (
              <Flex
                key={index}
                justify={message.role === 'user' ? 'flex-end' : 'flex-start'}
                mb={{ base: 3, md: 4 }}
              >
                <Box
                  maxW={{ base: "100%", md: "85%" }}
                  bg={message.role === 'user' ? colors.gradient : colors.surface}
                  color={message.role === 'user' ? 'white' : colors.text}
                  p={message.role === 'user' ? { base: 3, md: 4 } : { base: 3, md: 5 }}
                  borderRadius="2xl"
                  boxShadow={colors.shadow}
                  textAlign="left"
                  border="1px solid"
                  borderColor={message.role === 'user' ? 'transparent' : colors.cardBorder}
                  position="relative"
                  _before={message.role === 'user' ? {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    borderRadius: '2xl',
                    background: colors.gradient,
                    opacity: 0.9,
                    zIndex: -1,
                  } : {}}
                >
                {message.role === 'assistant' ? (
                  <Box position="relative">
                    <HStack spacing={2} mb={2} alignItems="center" justify="space-between">
                      <HStack spacing={2} alignItems="center">
                        <Image
                          src="/src/assets/mapit_logo_no_bg.png"
                          alt="MAPIT AI"
                          boxSize="24px"
                        />
                        <Text fontWeight="bold" color={colors.text}>MAPIT AI</Text>
                      </HStack>
                      <HStack spacing={2}>
                        {isStreaming && index === messages.length - 1 && (
                          <HStack spacing={1}>
                            <AnimatedSpinner size="12px" color={colors.primary} />
                            <Text fontSize="xs" color={colors.primary} fontWeight="medium">
                              Streaming
                            </Text>
                          </HStack>
                        )}
                        <Text fontSize="xs" color={colors.text + '80'} fontWeight="medium">
                          {new Date(message.timestamp).toLocaleString('en-GB', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                          })}
                        </Text>
                        <Tooltip label="Delete message pair" placement="top">
                          <IconButton
                            aria-label="Delete message pair"
                            icon={<FiX size={14} />}
                            size="xs"
                            variant="ghost"
                            color={colors.text + '60'}
                            _hover={{ 
                              color: colors.error,
                              bg: colors.error + '20',
                            }}
                            onClick={(e) => handleDeleteMessage(index, e)}
                            minW="auto"
                            h="auto"
                            p={1}
                          />
                        </Tooltip>
                      </HStack>
                    </HStack>
                    <Box 
                      className="prose prose-sm max-w-none" 
                      sx={{
                        'p': { marginBottom: '1em', textAlign: 'left' },
                        'ul': { marginBottom: '1em', paddingLeft: '1.5em', textAlign: 'left' },
                        'ol': { marginBottom: '1em', paddingLeft: '1.5em', textAlign: 'left' },
                        'li': { marginBottom: '0.5em', textAlign: 'left' },
                        'h1, h2, h3, h4': { 
                          marginTop: '1em', 
                          marginBottom: '0.5em', 
                          fontWeight: 'bold',
                          textAlign: 'left',
                          color: colors.primary
                        },
                        'code': { 
                          backgroundColor: 'gray.200',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.25em',
                          fontSize: '0.875em',
                          fontFamily: 'monospace'
                        },
                        'pre': {
                          backgroundColor: 'gray.200',
                          padding: '1em',
                          borderRadius: '0.5em',
                          overflowX: 'auto',
                          marginBottom: '1em',
                          textAlign: 'left'
                        },
                        'strong': { 
                          fontWeight: 'bold',
                          color: 'blue.600'
                        },
                        'em': { 
                          fontStyle: 'italic',
                          color: 'green.600'
                        },
                        'a': {
                          color: '#3182ce',
                          textDecoration: 'underline',
                          fontWeight: '500',
                          transition: 'all 0.2s ease-in-out',
                          _hover: {
                            color: '#2c5282',
                            textDecoration: 'none',
                            transform: 'translateY(-1px)',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                          }
                        },
                        'div': {
                          marginBottom: '1em',
                          borderRadius: '0.5em',
                          overflow: 'hidden'
                        },
                        'span': {
                          display: 'inline-block'
                        },
                        // Custom CSS classes for formatted content
                        '.formatted-content': {
                          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                          lineHeight: '1.7',
                          color: '#2d3748',
                          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
                          padding: '1.5em',
                          borderRadius: '1em',
                          boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
                          border: '1px solid rgba(102, 126, 234, 0.2)'
                        },
                        '.link': {
                          color: '#3182ce',
                          textDecoration: 'underline',
                          fontWeight: '500',
                          transition: 'all 0.2s ease-in-out',
                          _hover: {
                            color: '#2c5282',
                            textDecoration: 'none'
                          }
                        },
                        '.highlight': {
                          fontWeight: '700',
                          color: '#1a365d',
                          background: 'linear-gradient(120deg, #a8edea 0%, #fed6e3 100%)',
                          padding: '0.1em 0.3em',
                          borderRadius: '0.2em'
                        },
                        '.emphasis': {
                          fontStyle: 'italic',
                          color: '#2d3748',
                          background: 'linear-gradient(120deg, #ffecd2 0%, #fcb69f 100%)',
                          padding: '0.1em 0.3em',
                          borderRadius: '0.2em'
                        },
                        '.code': {
                          background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                          color: 'white',
                          padding: '0.2em 0.4em',
                          fontFamily: 'monospace',
                          borderRadius: '0.3em',
                          fontSize: '0.9em',
                          fontWeight: '500'
                        },
                        '.title': {
                          fontSize: '2em',
                          color: '#2d3748',
                          margin: '1.5em 0 0.8em',
                          borderBottom: '3px solid',
                          borderImage: 'linear-gradient(90deg, #3b82f6 0%, #06b6d4 100%) 1',
                          paddingBottom: '0.4em',
                          fontWeight: '700'
                        },
                        '.subtitle': {
                          fontSize: '1.6em',
                          color: '#4a5568',
                          margin: '1.2em 0 0.6em',
                          borderBottom: '2px solid',
                          borderImage: 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%) 1',
                          paddingBottom: '0.3em',
                          fontWeight: '600'
                        },
                        '.section': {
                          fontSize: '1.3em',
                          color: '#718096',
                          margin: '1em 0 0.5em',
                          fontWeight: '600',
                          background: 'linear-gradient(90deg, #a8edea 0%, #fed6e3 100%)',
                          padding: '0.3em 0.6em',
                          borderRadius: '0.3em',
                          display: 'inline-block'
                        },
                        '.list': {
                          listStyle: 'none',
                          margin: '1.2em 0',
                          paddingLeft: '0',
                          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
                          padding: '1em',
                          borderRadius: '0.5em',
                          borderLeft: '4px solid #3b82f6'
                        },
                        '.ordered-list': {
                          listStyle: 'none',
                          margin: '1.2em 0',
                          paddingLeft: '0',
                          background: 'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
                          padding: '1em',
                          borderRadius: '0.5em',
                          borderLeft: '4px solid #8ec5fc'
                        },
                        '.project-header': {
                          background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                          color: 'white',
                          padding: '1.2em',
                          margin: '1.5em 0',
                          borderRadius: '0.8em',
                          boxShadow: '0 4px 15px rgba(59, 130, 246, 0.3)'
                        },
                        '.field-label': {
                          color: '#3b82f6',
                          fontWeight: '700',
                          background: 'linear-gradient(120deg, #a8edea 0%, #fed6e3 100%)',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.3em',
                          marginRight: '0.5em'
                        },
                        '.partner': {
                          margin: '0.8em 0',
                          padding: '0.8em',
                          background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                          borderRadius: '0.5em',
                          color: 'white'
                        },
                        '.partner-type': {
                          opacity: '0.9'
                        },
                        '.partner-detail': {
                          margin: '0.4em 0',
                          padding: '0.5em',
                          background: 'rgba(255,255,255,0.2)',
                          borderRadius: '0.3em'
                        },
                        '.detail-label': {
                          fontWeight: '600',
                          color: '#fbbf24'
                        },
                        '.detail-value': {
                          color: 'white'
                        },
                        '.score': {
                          background: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
                          padding: '0.3em 0.6em',
                          borderRadius: '0.4em',
                          fontWeight: '600',
                          color: '#744210',
                          display: 'inline-block',
                          margin: '0.2em 0.5em 0.2em 0'
                        },
                        '.score-label': {
                          color: '#3b82f6'
                        },
                        '.score-value': {
                          fontFamily: 'monospace'
                        },
                        '.section-header': {
                          margin: '1em 0',
                          padding: '0.8em',
                          background: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
                          borderRadius: '0.5em',
                          borderLeft: '4px solid #3b82f6'
                        },
                        '.date': {
                          background: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.3em',
                          fontWeight: '500',
                          color: '#2d3748',
                          fontFamily: 'monospace'
                        },
                        '.status': {
                          background: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
                          padding: '0.3em 0.6em',
                          borderRadius: '0.4em',
                          fontWeight: '700',
                          color: '#744210',
                          textTransform: 'uppercase',
                          fontSize: '0.9em',
                          letterSpacing: '0.5px'
                        },
                        '.money': {
                          background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                          color: 'white',
                          padding: '0.3em 0.6em',
                          borderRadius: '0.4em',
                          fontWeight: '600',
                          fontFamily: 'monospace'
                        },
                        '.percentage': {
                          background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                          color: 'white',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.3em',
                          fontWeight: '600',
                          fontFamily: 'monospace'
                        },
                        '.eu-term': {
                          background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                          color: 'white',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.3em',
                          fontWeight: '600',
                          textTransform: 'uppercase',
                          fontSize: '0.9em',
                          letterSpacing: '0.5px'
                        },
                        '.project-id': {
                          background: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
                          padding: '0.2em 0.4em',
                          borderRadius: '0.3em',
                          fontWeight: '600',
                          color: '#2d3748',
                          fontFamily: 'monospace',
                          border: '1px solid #3b82f6'
                        }
                      }}
                    >
                      <Box
                        whiteSpace="pre-wrap"
                        dangerouslySetInnerHTML={{ 
                          __html: DOMPurify.sanitize(processMessageContent(message.content, message.contextData, true), {
                            ALLOWED_TAGS: ['span', 'strong', 'em', 'a', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'svg', 'path', 'circle'],
                            ALLOWED_ATTR: ['class', 'href', 'target', 'data-node-id', 'data-acronym', 'title', 'width', 'height', 'viewBox', 'fill', 'd', 'style', 'cx', 'cy', 'r'],
                            ALLOW_DATA_ATTR: true,
                            KEEP_CONTENT: true
                          }) 
                        }}
                      />
                      {isStreaming && index === messages.length - 1 && (
                        <Box
                          as="span"
                          display="inline-block"
                          width="2px"
                          height="1.2em"
                          bg={colors.primary}
                          ml={1}
                          animation="blink 1s infinite"
                          sx={{
                            '@keyframes blink': {
                              '0%, 50%': { opacity: 1 },
                              '51%, 100%': { opacity: 0 }
                            }
                          }}
                        />
                      )}
                      {message.chartData && (
                        <>
                          {console.log('Rendering ChartDisplay for message:', message.chartData)}
                          <ChartDisplay chartData={message.chartData} />
                        </>
                      )}
                      {message.contextData && (
                        <ReferencesDisplay 
                          contextData={message.contextData} 
                          content={message.content} 
                        />
                      )}
                    </Box>
                    {message.contextUsed && (
                      <HStack spacing={{ base: 0.5, md: 2 }} mt={3} borderTop="1px" borderColor="gray.200" pt={2} justify="space-between">
                        <HStack spacing={{ base: 0, md: 2 }}>
                          {(message.contextUsed.neo4j_planner || message.contextUsed.neo4j || (message.contextData?.neo4j_planner && message.contextData.neo4j_planner.length > 0) || (message.contextData?.neo4j && message.contextData.neo4j[0]?._query_type === 'planner_generated')) && (
                                                          <Tooltip label={`Neo4j Context (${getContextSize(message.contextData?.neo4j_planner || message.contextData?.neo4j)})`}>
                              <IconButton
                                aria-label="Neo4j Context"
                                icon={<FiDatabase />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#00d4aa"
                                _hover={{
                                  bg: 'rgba(0, 212, 170, 0.1)',
                                  color: '#00d4aa',
                                }}
                                onClick={() => {
                                  console.log('Neo4j icon clicked, message contextData:', message.contextData);
                                  console.log('Neo4j contextData:', message.contextData?.neo4j_planner || message.contextData?.neo4j);
                                  handleContextClick('neo4j', message.contextData?.neo4j_planner || message.contextData?.neo4j, message.contextSources);
                                }}
                              />
                            </Tooltip>
                          )}
                          {message.contextUsed.qdrant && (
                            <Tooltip label={`Qdrant Context (${getContextSize(message.contextData?.qdrant)})`}>
                              <IconButton
                                aria-label="Qdrant Context"
                                icon={<FiServer />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#ff6b6b"
                                _hover={{
                                  bg: 'rgba(255, 107, 107, 0.1)',
                                  color: '#ff6b6b',
                                }}
                                onClick={() => handleContextClick('qdrant', message.contextData?.qdrant, message.contextSources)}
                              />
                            </Tooltip>
                          )}
                          {message.contextUsed.elasticsearch && (
                            <Tooltip label={`Elasticsearch Context (${getContextSize(message.contextData?.elasticsearch)})`}>
                              <IconButton
                                aria-label="Elasticsearch Context"
                                icon={<FiGlobe />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#f39c12"
                                _hover={{
                                  bg: 'rgba(243, 156, 18, 0.1)',
                                  color: '#f39c12',
                                }}
                                onClick={() => handleContextClick('elasticsearch', message.contextData?.elasticsearch, message.contextSources)}
                              />
                            </Tooltip>
                          )}
                          {message.previousContextsIncluded && (
                            <HStack spacing={1}>
                              <Tooltip label="Previous contexts included in response">
                                <Box
                                  as="span"
                                  display="inline-flex"
                                  alignItems="center"
                                  justifyContent="center"
                                  width="16px"
                                  height="16px"
                                  borderRadius="full"
                                  bg="blue.500"
                                  color="white"
                                  fontSize="8px"
                                  fontWeight="bold"
                                  cursor="help"
                                >
                                  P
                                </Box>
                              </Tooltip>
                              <Tooltip label={`Total context size: ${getTotalContextLength(message.contextData, message.totalContextSizeBytes)}`}>
                                <Text
                                  fontSize="xs"
                                  color="blue.500"
                                  fontWeight="bold"
                                  cursor="help"
                                >
                                  {getTotalContextLength(message.contextData, message.totalContextSizeBytes)}
                                </Text>
                              </Tooltip>
                            </HStack>
                          )}
                          {message.contextUsed.ollama && (
                            <Tooltip label="Extracted Keywords">
                              <IconButton
                                aria-label="Ollama Context"
                                icon={<FiCpu />}
                                size="sm"
                                variant="ghost"
                                colorScheme="blue"
                                onClick={() => handleContextClick('ollama', message.contextData?.ollama, message.contextSources)}
                              />
                            </Tooltip>
                          )}
                          {message.lucene_query && (
                            <Tooltip label="Co-participation Network">
                              <IconButton
                                aria-label="Co-participation"
                                icon={<FiGitBranch />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#38a169"
                                _hover={{
                                  bg: 'rgba(56, 161, 105, 0.1)',
                                  color: '#38a169',
                                }}
                                onClick={() => handleCoParticipationClick(message.lucene_query || '')}
                                isLoading={coParticipationLoading}
                              />
                            </Tooltip>
                          )}
                          {message.lucene_query && (
                            <Tooltip label="Find Partners">
                              <IconButton
                                aria-label="Partner Finder"
                                icon={<FiUsers />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#e53e3e"
                                _hover={{
                                  bg: 'rgba(229, 62, 62, 0.1)',
                                  color: '#e53e3e',
                                }}
                                onClick={() => handlePartnerFinderClick(message.lucene_query || '')}
                                isLoading={partnerFinderLoading}
                              />
                            </Tooltip>
                          )}
                          {message.lucene_query && (
                            <Tooltip label="View Heatmap">
                              <IconButton
                                aria-label="Heatmap"
                                icon={<FiBarChart />}
                                size={{ base: "xs", md: "sm" }}
                                variant="ghost"
                                color="#06b6d4"
                                _hover={{
                                  bg: 'rgba(6, 182, 212, 0.1)',
                                  color: '#06b6d4',
                                }}
                                onClick={() => handleHeatmapClick(message.lucene_query || '')}
                                isLoading={heatmapLoading}
                              />
                            </Tooltip>
                          )}
                        </HStack>
                        <HStack 
                          spacing={1} 
                          fontSize="xs" 
                          color="gray.500"
                        >
                          {message.confidence && (
                            <Tooltip label={`${message.confidence.level.charAt(0).toUpperCase() + message.confidence.level.slice(1)} Confidence (${message.confidence.percentage}%)`}>
                              <Box
                                as="span"
                                display="inline-flex"
                                alignItems="center"
                                justifyContent="center"
                                width="12px"
                                height="12px"
                                borderRadius="full"
                                bg={message.confidence.level === 'high' ? 'green.500' : message.confidence.level === 'medium' ? 'orange.500' : 'red.500'}
                                boxShadow={`0 0 8px ${message.confidence.level === 'high' ? '#10b981' : message.confidence.level === 'medium' ? '#f59e0b' : '#ef4444'}`}
                                className="confidence-led"
                                cursor="help"
                              />
                            </Tooltip>
                          )}
                          {message.confidence && message.elapsedTime && (
                            <Box width="8px" />
                          )}
                          {message.elapsedTime && (
                            <>
                              <FiClock size={12} />
                              <Text>{message.elapsedTime.toFixed(1)}s</Text>
                            </>
                          )}
                          {message.tokenCounts && (
                            <Tooltip 
                              label={
                                <Box>
                                  <Text fontWeight="bold" mb={1}>Token Breakdown:</Text>
                                  <Text fontSize="xs">User question: {message.tokenCounts.user_question.toLocaleString()}</Text>
                                  <Text fontSize="xs">Planner prompt: {message.tokenCounts.planner_prompt.toLocaleString()}</Text>
                                  <Text fontSize="xs">Planner output: {message.tokenCounts.planner_output.toLocaleString()}</Text>
                                  <Text fontSize="xs">Context: {message.tokenCounts.context.toLocaleString()}</Text>
                                  <Text fontSize="xs">Previous context: {message.tokenCounts.prev_context.toLocaleString()}</Text>
                                  <Text fontSize="xs">Chat history: {message.tokenCounts.chat_history.toLocaleString()}</Text>
                                  <Text fontSize="xs">System instructions: {message.tokenCounts.system_instructions.toLocaleString()}</Text>
                                  <Text fontSize="xs">Final LLM output: {message.tokenCounts.final_llm_output.toLocaleString()}</Text>
                                  <Text fontSize="xs" fontWeight="bold" mt={1} borderTop="1px solid" pt={1}>
                                    Total: {message.tokenCounts.total.toLocaleString()}
                                  </Text>
                                </Box>
                              }
                              hasArrow
                              placement="top"
                            >
                              <HStack spacing={1} cursor="help">
                                <FiHash size={12} />
                                <Text>{message.tokenCounts.total.toLocaleString()}</Text>
                              </HStack>
                            </Tooltip>
                          )}
                          <Tooltip label="Copy response and references to clipboard">
                            <IconButton
                              aria-label="Copy to clipboard"
                              icon={<FiCopy size={12} />}
                              size={{ base: "xs", md: "sm" }}
                              variant="ghost"
                              color="gray.500"
                              _hover={{
                                bg: 'rgba(128, 128, 128, 0.1)',
                                color: 'gray.700',
                              }}
                              onClick={async () => {
                                const success = await copyResponseToClipboard(message, message.contextData, message.content);
                                if (success) {
                                  toast({
                                    title: "Copied!",
                                    description: "Response and references copied to clipboard.",
                                    status: "success",
                                    duration: 2000,
                                    isClosable: true,
                                    position: "top-right",
                                  });
                                } else {
                                  toast({
                                    title: "Copy Failed",
                                    description: "Failed to copy to clipboard.",
                                    status: "error",
                                    duration: 3000,
                                    isClosable: true,
                                    position: "top-right",
                                  });
                                }
                              }}
                            />
                          </Tooltip>
                        </HStack>
                      </HStack>
                    )}
                  </Box>
                ) : (
                  <Box position="relative">
                    <HStack spacing={2} mb={1.5} alignItems="center" justify="space-between">
                      <HStack spacing={2} alignItems="center">
                        <Icon as={FiUser} boxSize="20px" color="white" />
                        <Text fontWeight="bold" color="white">You</Text>
                      </HStack>
                      <HStack spacing={2}>
                        <Text fontSize="xs" color="white" fontWeight="medium">
                          {new Date(message.timestamp).toLocaleString('en-GB', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                          })}
                        </Text>
                        {/* Show delete button for orphaned user messages (no following assistant message) */}
                        {(index === messages.length - 1 || messages[index + 1]?.role !== 'assistant') && (
                          <Tooltip label="Delete orphaned message" placement="top">
                            <IconButton
                              aria-label="Delete orphaned message"
                              icon={<FiX size={14} />}
                              size="xs"
                              variant="ghost"
                              color="white"
                              _hover={{ 
                                color: "red.200",
                                bg: "rgba(255, 255, 255, 0.1)",
                              }}
                              onClick={(e) => handleDeleteOrphanedMessage(index, e)}
                              minW="auto"
                              h="auto"
                              p={1}
                            />
                          </Tooltip>
                        )}
                      </HStack>
                    </HStack>
                    <Box
                      whiteSpace="pre-wrap"
                      textAlign="left"
                      dangerouslySetInnerHTML={{ 
                        __html: DOMPurify.sanitize(processMessageContent(message.content, message.contextData, false), {
                          ALLOWED_TAGS: ['span', 'strong', 'em', 'a', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre'],
                          ALLOWED_ATTR: ['class', 'href', 'target'],
                          ALLOW_DATA_ATTR: true,
                          KEEP_CONTENT: true
                        }) 
                      }}
                    />
                  </Box>
                )}
                </Box>
              </Flex>
            ))
            )}
            {/* Scroll target for auto-scrolling */}
            <div ref={messagesEndRef} />
          </Box>
          {/* Input Area - Fixed at bottom */}
          <Box
            position="fixed"
            bottom="20px"
            left={{ base: "10px", sm: "10px", lg: "250px" }}
            right={{ base: "10px", sm: "10px", lg: "280px" }}
            zIndex={20}
            px={{ base: 0, sm: 4, md: 6, lg: 8 }}
          >
            <VStack spacing={2}>
              {/* Progress Indicator */}
              {isLoading && (
                <HStack 
                  spacing={3} 
                  bg={colors.cardBg}
                  borderRadius="lg"
                  p={2}
                  border="1px solid"
                  borderColor={colors.cardBorder}
                  boxShadow={colors.shadow}
                >
                  <HStack spacing={1}>
                    <Icon 
                      as={FiCpu} 
                      size="xs" 
                      color={progressStage === 'llm1' ? colors.primary : colors.text + '40'}
                    />
                    <Text fontSize="xs" color={progressStage === 'llm1' ? colors.primary : colors.text + '60'}>
                      Planner 
                    </Text>
                  </HStack>
                  <Text fontSize="xs" color={colors.text + '40'}>→</Text>
                  <HStack spacing={1}>
                    <Icon 
                      as={FiDatabase} 
                      size="xs" 
                      color={progressStage === 'data_retrieval' ? '#00d4aa' : colors.text + '40'}
                    />
                    <Text fontSize="xs" color={progressStage === 'data_retrieval' ? '#00d4aa' : colors.text + '60'}>
                      Data Retrieval
                    </Text>
                  </HStack>
                  <Text fontSize="xs" color={colors.text + '40'}>→</Text>
                  <HStack spacing={1}>
                    <Icon 
                      as={FiCpu} 
                      size="xs" 
                      color={progressStage === 'llm2' ? colors.primary : colors.text + '40'}
                    />
                    <Text fontSize="xs" color={progressStage === 'llm2' ? colors.primary : colors.text + '60'}>
                      Answerer
                    </Text>
                  </HStack>
                </HStack>
              )}
              
              {/* Input and Send Button */}
              <Flex 
                direction="column"
                minW="100%"
                maxW="100%"
                bg={colors.cardBg}
                borderRadius="2xl"
                border="1px solid"
                borderColor={colors.cardBorder}
                p={{ base: 3, sm: 3, md: 4 }}
                boxShadow={colors.shadowLg}
                backdropFilter="blur(10px)"
              >
                              <Flex direction={["column", "row"]} gap={[3, 4]} w="100%">
                <Textarea
                  value={input}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value)}
                  onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
                  placeholder="Ask MAPIT AI anything about EU funding opportunities..."
                  size="lg"
                  flex="1"
                  bg={colors.inputBg}
                  borderColor={colors.inputBorder}
                  color={colors.text}
                  _placeholder={{ color: colors.text + '60' }}
                  borderRadius="xl"
                  _hover={{
                    borderColor: colors.primary,
                  }}
                  _focus={{
                    borderColor: colors.primary,
                    boxShadow: `0 0 0 1px ${colors.primary}30`,
                  }}
                  minW="0"
                  w="100%"
                  fontSize={{ base: "sm", md: "md" }}
                  resize="none"
                  rows={3}
                  py={{ base: 2, md: 3 }}
                />
                  <Flex direction="column" align="flex-end" gap={2} w={{ base: "auto", md: "auto" }} minW={{ base: "120px", md: "auto" }}>
                    <Button
                      bg={isLoading ? (isHovering ? colors.error : colors.gradient) : colors.gradient}
                      color="white"
                      onClick={isLoading ? handleStopRequest : handleSendMessage}
                      isLoading={false}
                      leftIcon={isLoading ? <FiStopCircle /> : <FiSend />}
                      onMouseEnter={() => setIsHovering(true)}
                      onMouseLeave={() => setIsHovering(false)}
                      _hover={{
                        bg: isLoading ? colors.error : colors.gradientDark,
                        transform: 'translateY(-2px)',
                        boxShadow: colors.shadowLg,
                      }}
                      _active={{
                        transform: 'translateY(0)',
                      }}
                      transition="all 0.2s ease-in-out"
                      position="relative"
                      minW="120px"
                      w={{ base: "120px", md: "auto" }}
                      borderRadius="xl"
                      fontWeight="semibold"
                      fontSize={{ base: "sm", md: "md" }}
                      size="lg"
                    >
                      {isLoading ? (isHovering ? 'STOP' : (isStreaming ? (
                        <HStack spacing={1}>
                          <AnimatedSpinner size="14px" color="white" />
                          <Text>Streaming</Text>
                        </HStack>
                      ) : 'Sending...')) : 'Send'}
                    </Button>
                    
                    {/* Previous Context is always SMART - removed user control */}
                  </Flex>
                </Flex>
              </Flex>
            </VStack>
          </Box>
        </Box>
      </Flex>

      {/* Mobile Left Drawer - Chat History */}
      <Drawer isOpen={isLeftDrawerOpen} placement="left" onClose={onLeftDrawerClose} size="full">
        <DrawerOverlay />
        <DrawerContent bg={colors.sidebarBg}>
          <DrawerCloseButton color={colors.text} />
          <DrawerHeader borderBottomWidth="1px" borderColor={colors.sidebarBorder}>
            <HStack spacing={3}>
              <Icon as={FiMenu} />
              <Text fontSize="lg" fontWeight="bold" color={colors.text}>
                Chat Sessions
              </Text>
            </HStack>
          </DrawerHeader>
          <DrawerBody p={4}>
            <VStack spacing={4} align="stretch">
              <Flex justify="space-between" align="center">
                <Text 
                  fontSize="md" 
                  fontWeight="bold" 
                  color={colors.text}
                  textTransform="uppercase"
                  letterSpacing="wide"
                >
                  Chat Sessions
                </Text>
                <IconButton
                  aria-label="New chat"
                  icon={<FiPlus />}
                  size="md"
                  onClick={() => {
                    createNewSession();
                    onLeftDrawerClose();
                  }}
                  bg={colors.primary}
                  color="white"
                  borderRadius="lg"
                  w="40px"
                  h="40px"
                  _hover={{ 
                    bg: colors.primaryHover,
                    transform: 'translateY(-2px)',
                    boxShadow: colors.shadowLg,
                  }}
                  transition="all 0.2s ease-in-out"
                />
              </Flex>
              <VStack 
                spacing={2} 
                align="stretch" 
                overflowY="auto" 
                flex="1" 
                pr={1}
                css={{
                  '&::-webkit-scrollbar': {
                    width: '4px',
                  },
                  '&::-webkit-scrollbar-track': {
                    background: 'transparent',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    background: colors.text + '20',
                    borderRadius: '4px',
                  },
                  '&::-webkit-scrollbar-thumb:hover': {
                    background: colors.text + '40',
                  },
                }}
              >
                {chatSessions
                  .sort((a, b) => {
                    // First priority: new sessions (force to top)
                    if ((a as any).isNew && !(b as any).isNew) return -1;
                    if (!(a as any).isNew && (b as any).isNew) return 1;
                    
                    // Sort by last message time, then by updated time, then by creation time (newest first)
                    const aLastMessageTime = a.lastMessageAt ? new Date(a.lastMessageAt).getTime() : 0;
                    const bLastMessageTime = b.lastMessageAt ? new Date(b.lastMessageAt).getTime() : 0;
                    
                    const aUpdatedTime = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
                    const bUpdatedTime = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
                    
                    const aCreatedTime = a.createdAt ? new Date(a.createdAt).getTime() : 0;
                    const bCreatedTime = b.createdAt ? new Date(b.createdAt).getTime() : 0;
                    
                    // Second priority: last message time (most recent activity)
                    if (aLastMessageTime !== bLastMessageTime) {
                      return bLastMessageTime - aLastMessageTime;
                    }
                    
                    // Third priority: updated time
                    if (aUpdatedTime !== bUpdatedTime) {
                      return bUpdatedTime - aUpdatedTime;
                    }
                    
                    // Fourth priority: creation time (newest first)
                    if (aCreatedTime !== bCreatedTime) {
                      return bCreatedTime - aCreatedTime;
                    }
                    
                    // Fallback: sort by session ID (newer IDs first)
                    return b.id.localeCompare(a.id);
                  })
                  .map(session => (
                  <Box
                    key={session.id}
                    position="relative"
                    _hover={{ 
                      bg: colors.hoverBg,
                      transform: 'translateX(2px)',
                    }}
                    cursor="pointer"
                    onClick={() => {
                      handleSelectChat(session.id);
                      onLeftDrawerClose();
                    }}
                    bg={currentSessionId === session.id ? colors.activeBg : 'transparent'}
                    p={3}
                    borderRadius="lg"
                    border="1px solid"
                    borderColor={currentSessionId === session.id ? colors.primary : 'transparent'}
                    transition="all 0.2s ease-in-out"
                    boxShadow={currentSessionId === session.id ? colors.shadow : 'none'}
                    minH="auto"
                  >
                    <VStack align="start" spacing={1} width="100%">
                      {editingTitle === session.id ? (
                        <form onSubmit={(e) => handleSaveTitle(session.id, e)} style={{ width: '100%' }}>
                          <Input
                            value={editedTitle}
                            onChange={(e) => setEditedTitle(e.target.value)}
                            size="xs"
                            autoFocus
                            onBlur={() => setEditingTitle(null)}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === 'Escape') {
                                setEditingTitle(null)
                              }
                            }}
                            bg={colors.inputBg}
                            borderColor={colors.inputBorder}
                            color={colors.text}
                            _placeholder={{ color: colors.text + '60' }}
                            borderRadius="md"
                            fontSize="xs"
                          />
                        </form>
                      ) : (
                        <Flex align="center" justify="space-between" width="100%">
                          <VStack align="start" spacing={0} flex={1} minW={0}>
                            <Text
                              fontSize="sm"
                              fontWeight="medium"
                              noOfLines={2}
                              color={colors.text}
                              lineHeight="1.2"
                            >
                              {session.title}
                            </Text>
                            <Text fontSize="xs" color={colors.text + '60'} lineHeight="1.1">
                              {session.lastMessageAt 
                                ? new Date(session.lastMessageAt).toLocaleDateString() 
                                : (session.createdAt ? new Date(session.createdAt).toLocaleDateString() : 'No messages')}
                            </Text>
                          </VStack>
                          <HStack spacing={1} ml={2} flexShrink={0}>
                            <IconButton
                              aria-label="Edit title"
                              icon={<FiEdit2 size={12} />}
                              size="xs"
                              variant="ghost"
                              color={colors.text + '80'}
                              _hover={{ 
                                color: colors.primary,
                                bg: colors.hoverBg,
                              }}
                              onClick={(e) => handleStartEdit(session.id, session.title, e)}
                              minW="auto"
                              h="auto"
                              p={1}
                            />
                            <IconButton
                              aria-label="Remove chat"
                              icon={<FiX size={12} />}
                              size="xs"
                              variant="ghost"
                              onClick={(e) => handleRemoveChat(session.id, e)}
                              color={colors.text + '80'}
                              _hover={{ 
                                color: colors.error,
                                bg: colors.error + '20',
                              }}
                              minW="auto"
                              h="auto"
                              p={1}
                            />
                          </HStack>
                        </Flex>
                      )}
                    </VStack>
                  </Box>
                ))}
              </VStack>
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      {/* Mobile Right Drawer - System Tools */}
      <Drawer isOpen={isRightDrawerOpen} placement="right" onClose={onRightDrawerClose} size="full">
        <DrawerOverlay />
        <DrawerContent bg={colors.sidebarBg}>
          <DrawerCloseButton color={colors.text} />
          <DrawerHeader borderBottomWidth="1px" borderColor={colors.sidebarBorder}>
            <HStack spacing={3}>
              <Icon as={FiCpu} />
              <Text fontSize="lg" fontWeight="bold" color={colors.text}>
                System Tools
              </Text>
            </HStack>
          </DrawerHeader>
          <DrawerBody p={4}>
            <VStack spacing={6} align="stretch">
              <Box>
                <SystemHealthComponent />
              </Box>
              <Divider borderColor={colors.sidebarBorder} />
              <Box>
                <NodeVisualizer />
              </Box>
              <Divider borderColor={colors.sidebarBorder} />
              <Box>
                <CoParticipationBox />
              </Box>
              <Divider borderColor={colors.sidebarBorder} />
              <Box>
                <PartnerFinderBox />
              </Box>
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      {/* Partner Results Modal */}
      <PartnerResultsModal
        isOpen={showPartnerResultsModal}
        onClose={() => setShowPartnerResultsModal(false)}
        partners={partnerResults}
        luceneQuery={partnerResultsLuceneQuery}
        originalQuery={partnerResultsOriginalQuery}
        expandedQuery={partnerResultsExpandedQuery}
      />

      {/* Heatmap Modal */}
      <HeatmapModal
        isOpen={showHeatmapModal}
        onClose={() => setShowHeatmapModal(false)}
        data={heatmapData}
        luceneQuery={heatmapLuceneQuery}
        metric={heatmapMetric}
      />
    </Box>
  )
} 