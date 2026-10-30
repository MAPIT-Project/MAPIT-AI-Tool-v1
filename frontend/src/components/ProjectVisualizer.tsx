import React, { useState, useEffect } from 'react';
import { Box, Input, Button, Text, VStack } from '@chakra-ui/react';
import { apiPost } from '../utils/api';
import { FiShare2, FiAlertCircle, FiTarget } from 'react-icons/fi';
import { useThemeColors } from '../hooks/useThemeColors';

interface NodeVisualizerProps {
  className?: string;
}

const NodeVisualizer: React.FC<NodeVisualizerProps> = ({ className }) => {
  const colors = useThemeColors();
  const [nodeId, setNodeId] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isButtonHighlighted, setIsButtonHighlighted] = useState(false);

  // Listen for custom event to fill the input from chat
  useEffect(() => {
    console.log('Setting up fillNodeVisualizer event listener');
    
    const handleFillNodeVisualizer = (event: CustomEvent) => {
      console.log('fillNodeVisualizer event received:', event);
      const { nodeId: newNodeId, acronym } = event.detail;
      console.log('Received fillNodeVisualizer event:', { nodeId: newNodeId, acronym });
      setNodeId(newNodeId);
      setError(''); // Clear any previous errors
      console.log('Node ID set to:', newNodeId);
      
      // Highlight the button for 1 second
      setIsButtonHighlighted(true);
      setTimeout(() => {
        setIsButtonHighlighted(false);
      }, 1000);
    };

    // Add event listener
    window.addEventListener('fillNodeVisualizer', handleFillNodeVisualizer as EventListener);
    console.log('Event listener added for fillNodeVisualizer');

    // Cleanup
    return () => {
      console.log('Removing fillNodeVisualizer event listener');
      window.removeEventListener('fillNodeVisualizer', handleFillNodeVisualizer as EventListener);
    };
  }, []);

  // Also add a global event listener as fallback
  useEffect(() => {
    console.log('Setting up global fillNodeVisualizer event listener');
    
    const handleGlobalFillNodeVisualizer = (event: any) => {
      console.log('Global fillNodeVisualizer event received:', event);
      if (event.detail && event.detail.nodeId) {
        console.log('Setting nodeId from global event:', event.detail.nodeId);
        setNodeId(event.detail.nodeId);
        setError('');
        
        // Highlight the button for 1 second
        setIsButtonHighlighted(true);
        setTimeout(() => {
          setIsButtonHighlighted(false);
        }, 1000);
      }
    };

    // Add global event listener
    document.addEventListener('fillNodeVisualizer', handleGlobalFillNodeVisualizer);
    console.log('Global event listener added for fillNodeVisualizer');

    // Cleanup
    return () => {
      console.log('Removing global fillNodeVisualizer event listener');
      document.removeEventListener('fillNodeVisualizer', handleGlobalFillNodeVisualizer);
    };
  }, []);

  // Add CSS for button highlight animation
  useEffect(() => {
    // Add the pulse animation CSS if it doesn't exist
    if (!document.getElementById('button-pulse-animation-style')) {
      const style = document.createElement('style');
      style.id = 'button-pulse-animation-style';
      style.textContent = `
        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.05); }
          100% { transform: scale(1); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const handleVisualize = async () => {
    try {
      setError('');
      setIsLoading(true);
      const response = await apiPost('/node/visualize', {
        node_id: nodeId
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Log the response data for debugging
      console.log('Visualization data:', data);

      // Validate the response data
      if (!data || !data.nodes || !data.edges) {
        setError('Invalid visualization data received');
        return;
      }

      // Create a new window for visualization
      const visualizationWindow = window.open('', '_blank');
      if (!visualizationWindow) {
        setError('Please allow pop-ups for this website');
        return;
      }

      // Write the visualization HTML
      visualizationWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Node Visualization</title>
          <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
          <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.css" rel="stylesheet" type="text/css" />
          <style>
            body {
              margin: 0;
              padding: 0;
              font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
              background-color: #0a0e1a;
              color: #e2e8f0;
            }
            #header {
              background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
              padding: 4px;
              color: white;
              text-align: center;
              box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            #header h1 {
              margin: 0;
              font-size: 14px;
              font-weight: 600;
              text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            }
            #container {
              display: flex;
              height: calc(100vh - 60px);
              background-color: #1e293b;
              margin: 20px;
              border-radius: 16px;
              box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2);
              overflow: hidden;
              border: 1px solid #334155;
            }
            #network {
              flex: 1;
              background-color: #1e293b;
              border-radius: 16px;
              padding-bottom: 80px;
            }
            #details-panel {
              width: 350px;
              background: #334155;
              border-left: 1px solid #475569;
              padding: 25px;
              overflow-y: auto;
              display: none;
              box-shadow: -2px 0 5px rgba(0,0,0,0.2);
            }
            #details-panel h2 {
              margin-top: 0;
              color: #e2e8f0;
              font-size: 22px;
              font-weight: 600;
              padding-bottom: 15px;
              border-bottom: 2px solid #475569;
            }
            #details-panel p {
              margin: 12px 0;
              color: #cbd5e1;
              line-height: 1.6;
            }
            #details-panel strong {
              color: #60a5fa;
              font-weight: 600;
            }
            #details-panel ul {
              margin: 10px 0;
              padding-left: 20px;
            }
            #details-panel li {
              margin: 8px 0;
              color: #cbd5e1;
            }
            #controls {
              position: absolute;
              bottom: 20px;
              left: 20px;
              display: flex;
              flex-direction: row;
              gap: 12px;
              z-index: 1000;
              align-items: center;
            }
            #zoom-controls {
              background: #334155;
              padding: 12px;
              border-radius: 12px;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
              display: flex;
              flex-direction: row;
              gap: 6px;
              border: 1px solid #475569;
            }
            #level-control {
              background: #334155;
              padding: 12px 16px;
              border-radius: 12px;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
              display: flex;
              flex-direction: column;
              gap: 6px;
              width: 180px;
              border: 1px solid #475569;
            }
            #level-control label {
              font-size: 12px;
              color: #e2e8f0;
              font-weight: 600;
              display: flex;
              justify-content: space-between;
              align-items: center;
            }
            #level-control label span {
              color: #94a3b8;
              font-size: 11px;
            }
            #level-slider {
              width: 100%;
              height: 6px;
              -webkit-appearance: none;
              background: #475569;
              border-radius: 3px;
              outline: none;
              margin: 8px 0;
            }
            #level-slider::-webkit-slider-thumb {
              -webkit-appearance: none;
              width: 18px;
              height: 18px;
              background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
              border-radius: 50%;
              cursor: pointer;
              transition: all 0.2s;
              box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            #level-slider::-webkit-slider-thumb:hover {
              transform: scale(1.1);
              box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }
            #level-value {
              font-size: 11px;
              color: #94a3b8;
              text-align: center;
              font-weight: 500;
            }
            #zoom-controls button {
              width: 36px;
              height: 36px;
              border: none;
              background: #475569;
              border-radius: 8px;
              cursor: pointer;
              font-size: 16px;
              color: #e2e8f0;
              display: flex;
              align-items: center;
              justify-content: center;
              transition: all 0.2s ease;
              box-shadow: 0 1px 3px rgba(0,0,0,0.2);
              border: 1px solid #64748b;
            }
            #zoom-controls button:hover {
              background: #64748b;
              transform: translateY(-1px);
              box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            #zoom-controls button:active {
              transform: translateY(0);
              box-shadow: 0 1px 2px rgba(0,0,0,0.2);
            }
            #copy-controls {
              background: #334155;
              padding: 12px;
              border-radius: 12px;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
              display: flex;
              flex-direction: row;
              gap: 6px;
              border: 1px solid #475569;
            }
            #copy-controls button {
              width: 36px;
              height: 36px;
              border: none;
              background: #475569;
              border-radius: 8px;
              cursor: pointer;
              font-size: 16px;
              color: #e2e8f0;
              display: flex;
              align-items: center;
              justify-content: center;
              transition: all 0.2s ease;
              box-shadow: 0 1px 3px rgba(0,0,0,0.2);
              border: 1px solid #64748b;
            }
            #copy-controls button:hover {
              background: #64748b;
              transform: translateY(-1px);
              box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            #copy-controls button:active {
              transform: translateY(0);
              box-shadow: 0 1px 2px rgba(0,0,0,0.2);
            }

            #error {
              color: #f87171;
              padding: 15px;
              margin: 20px;
              background: #991b1b;
              border-radius: 12px;
              box-shadow: 0 4px 6px rgba(0,0,0,0.3);
              display: none;
              border: 1px solid #dc2626;
            }
            .vis-network {
              outline: none;
            }
            .vis-tooltip {
              background-color: #1e293b;
              color: #e2e8f0;
              padding: 10px 14px;
              border-radius: 8px;
              font-size: 14px;
              box-shadow: 0 4px 6px rgba(0,0,0,0.3);
              border: 1px solid #475569;
            }
          </style>
        </head>
        <body>
          <div id="header">
            <h3 id="project-title" style={{ fontSize: '10px', margin: '0px' }}>Node Visualization</h3>
          </div>
          <div id="container">
            <div id="network"></div>
            <div id="details-panel">
              <h2>Node Details</h2>
              <div id="node-details"></div>
            </div>
          </div>
          <div id="controls">
            <div id="level-control">
              <label>
                Visualization Depth
              </label>
              <input type="range" id="level-slider" min="0" max="2" value="2" step="1">
              <div id="level-value">Depth 2</div>
            </div>
            <div id="zoom-controls">
              <button id="zoom-in" title="Zoom In">+</button>
              <button id="zoom-out" title="Zoom Out">−</button>
              <button id="zoom-fit" title="Fit to Screen">⟲</button>
            </div>
            <div id="copy-controls">
              <button id="copy-graph" title="Copy Graph to Clipboard">📋</button>
            </div>
          </div>

          <div id="error"></div>
          <script>
            try {
              const data = ${JSON.stringify(data)};
              console.log('Visualization data:', data);
              console.log('Number of nodes:', data.nodes ? data.nodes.length : 0);
              console.log('Number of edges:', data.edges ? data.edges.length : 0);
              
              if (!data.nodes || !data.edges) {
                throw new Error('Invalid data structure');
              }
              
              // Log depth distribution
              const depthCounts = {};
              data.nodes.forEach(node => {
                const depth = node.depth || 0;
                depthCounts[depth] = (depthCounts[depth] || 0) + 1;
              });
              console.log('Depth distribution:', depthCounts);
              
              // Log edge depth distribution
              const edgeDepthCounts = {};
              data.edges.forEach(edge => {
                const depth = edge.depth || 1;
                edgeDepthCounts[depth] = (edgeDepthCounts[depth] || 0) + 1;
              });
              console.log('Edge depth distribution:', edgeDepthCounts);
              
              // Log sample nodes for each depth
              for (let depth = 0; depth <= 2; depth++) {
                const nodesAtDepth = data.nodes.filter(node => (node.depth || 0) === depth);
                console.log('Sample nodes at depth ' + depth + ':', nodesAtDepth.slice(0, 3));
              }

              // Find the main root node (depth 0)
              let mainNode = data.nodes.find(node => node.depth === 0);
              if (!mainNode) {
                // Fallback: find by type
                const fallbackNode = data.nodes.find(node => node.type === data.node_type || node.type === 'Project' || node.type === 'Organization' || node.type === 'Publication');
                if (fallbackNode) {
                  console.log('Using fallback node detection');
                  mainNode = fallbackNode;
                }
              }
              
              if (mainNode) {
                console.log('Main node found:', mainNode);
                document.getElementById('project-title').textContent = mainNode.label;
                // Set the browser tab title to the main node's label
                document.title = mainNode.label + ' - Node Visualization';
              } else {
                console.error('No main node found!');
                throw new Error('No main node found in the data');
              }

              // Function to filter nodes and edges based on depth level
              function filterByLevel(level) {
                console.log('Filtering by level:', level);
                
                if (level === 0) {
                  // Only show root node
                  return {
                    nodes: [mainNode],
                    edges: []
                  };
                }
                
                // Filter nodes by depth
                const filteredNodes = data.nodes.filter(node => {
                  const nodeDepth = node.depth || 0;
                  return nodeDepth <= level;
                });
                
                // Filter edges by depth
                const filteredEdges = data.edges.filter(edge => {
                  const edgeDepth = edge.depth || 1;
                  return edgeDepth <= level;
                });
                
                console.log('Filtered nodes:', filteredNodes.length, 'Filtered edges:', filteredEdges.length);
                
                // Log detailed breakdown
                const nodeDepthBreakdown = {};
                filteredNodes.forEach(node => {
                  const depth = node.depth || 0;
                  nodeDepthBreakdown[depth] = (nodeDepthBreakdown[depth] || 0) + 1;
                });
                console.log('Filtered node depth breakdown:', nodeDepthBreakdown);
                
                const edgeDepthBreakdown = {};
                filteredEdges.forEach(edge => {
                  const depth = edge.depth || 1;
                  edgeDepthBreakdown[depth] = (edgeDepthBreakdown[depth] || 0) + 1;
                });
                console.log('Filtered edge depth breakdown:', edgeDepthBreakdown);
                
                return {
                  nodes: filteredNodes,
                  edges: filteredEdges
                };
              }

              // Create initial visualization
              let currentLevel = 2;
              let network = null;
              
              function updateVisualization(level) {
                console.log('Updating visualization for level:', level);
                
                // Filter data based on the selected depth level
                const filteredData = level === 0 ? { nodes: [mainNode], edges: [] } : filterByLevel(level);
                
                console.log('Filtered data:', filteredData);
                
                // Use a Map to ensure unique nodes
                const uniqueNodes = new Map();
                console.log('Processing nodes:', filteredData.nodes.length);
                
                filteredData.nodes.forEach(node => {
                  if (!uniqueNodes.has(node.id)) {
                    // Get node depth for styling
                    const nodeDepth = node.depth || 0;
                    console.log('Processing node:', node.id, 'with depth:', nodeDepth);
                    
                    // Create depth-based styling
                    let nodeStyle = {
                      id: node.id,
                      label: node.label,
                      group: nodeDepth === 0 ? 'Project' : node.type, // Root nodes (depth=0) always use Project group (red)
                      originalType: node.type, // Preserve the original type for display purposes
                      title: \`\${node.label} (Depth: \${nodeDepth})\`,
                      font: { 
                        size: nodeDepth === 0 ? 16 : nodeDepth === 1 ? 14 : 12,
                        face: 'Segoe UI',
                        color: '#2c3e50',
                        bold: nodeDepth === 0
                      },
                      shape: 'box',
                      margin: 15,
                      widthConstraint: {
                        minimum: 120,
                        maximum: 250
                      },
                      shadow: {
                        enabled: true,
                        color: 'rgba(0,0,0,0.1)',
                        size: nodeDepth === 0 ? 8 : 5,
                        x: 2,
                        y: 2
                      },
                      borderWidth: nodeDepth === 0 ? 3 : nodeDepth === 1 ? 2 : 1,
                      borderDashes: nodeDepth === 2 ? [5, 5] : false
                    };
                    
                    uniqueNodes.set(node.id, nodeStyle);
                  }
                });
                
                console.log('Unique nodes created:', uniqueNodes.size);

                // Create nodes array from unique nodes
                const nodes = new vis.DataSet(Array.from(uniqueNodes.values()));

                // Create edges array
                console.log('Processing edges:', filteredData.edges.length);
                const edges = new vis.DataSet(filteredData.edges.map(edge => {
                  // Special styling for PARTICIPATES_IN relationships
                  const isParticipatesIn = edge.type === 'PARTICIPATES_IN';
                  const edgeDepth = edge.depth || 1;
                  
                  // Create depth-based edge styling
                  let edgeStyle = {
                    from: edge.source,
                    to: edge.target,
                    label: edge.type,
                    role: edge.role,
                    ecContribution: edge.ecContribution,
                    totalCost: edge.totalCost,
                    depth: edgeDepth,
                    arrows: {
                      to: {
                        enabled: true,
                        type: 'arrow',
                        scaleFactor: 0.8
                      }
                    },
                    font: { 
                      size: isParticipatesIn ? 14 : (edgeDepth === 1 ? 12 : 10),
                      face: 'Segoe UI',
                      color: isParticipatesIn ? '#dc2626' : (edgeDepth === 1 ? '#495057' : '#6b7280'),
                      strokeWidth: 0,
                      bold: isParticipatesIn
                    },
                    color: {
                      color: isParticipatesIn ? '#dc2626' : (edgeDepth === 1 ? '#6c757d' : '#9ca3af'),
                      highlight: isParticipatesIn ? '#991b1b' : '#2c3e50',
                      hover: isParticipatesIn ? '#991b1b' : '#2c3e50'
                    },
                    width: isParticipatesIn ? 3 : (edgeDepth === 1 ? 1.5 : 1),
                    smooth: {
                      type: 'curvedCW',
                      roundness: 0.2
                    }
                  };
                  
                  // Add dashed style for depth 2 edges (except PARTICIPATES_IN)
                  if (edgeDepth === 2 && !isParticipatesIn) {
                    edgeStyle.dashes = [5, 5];
                  }
                  
                  return edgeStyle;
                }));

                // Create or update network
                const container = document.getElementById('network');
                const networkData = { nodes, edges };
                const options = {
                  groups: {
                    Project: { 
                      color: { background: '#ef4444', border: '#dc2626' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Organization: { 
                      color: { background: '#f59e0b', border: '#d97706' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Publication: { 
                      color: { background: '#10b981', border: '#059669' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Deliverable: { 
                      color: { background: '#3b82f6', border: '#2563eb' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Topic: { 
                      color: { background: '#3b82f6', border: '#2563eb' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Call: { 
                      color: { background: '#ec4899', border: '#db2777' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    },
                    Sub: { 
                      color: { background: '#6b7280', border: '#4b5563' },
                      shape: 'box',
                      shadow: true,
                      font: { color: '#ffffff', size: 14, face: 'Segoe UI', bold: true }
                    }
                  },
                  physics: {
                    stabilization: true,
                    barnesHut: {
                      gravitationalConstant: -80000,
                      springConstant: 0.001,
                      springLength: 200
                    }
                  },
                  layout: {
                    improvedLayout: true,
                    randomSeed: 42
                  },
                  interaction: {
                    hover: true,
                    tooltipDelay: 200,
                    zoomView: true,
                    dragView: true
                  },
                  nodes: {
                    borderWidth: 2,
                    borderWidthSelected: 3,
                    shadow: true
                  },
                  edges: {
                    width: 1.5,
                    selectionWidth: 2,
                    hoverWidth: 2
                  }
                };

                if (network) {
                  network.setData(networkData);
                } else {
                  network = new vis.Network(container, networkData, options);
                  
                  // Set up zoom controls
                  document.getElementById('zoom-in').onclick = function() {
                    const scale = network.getScale();
                    network.moveTo({ scale: scale * 1.2 });
                  };

                  document.getElementById('zoom-out').onclick = function() {
                    const scale = network.getScale();
                    network.moveTo({ scale: scale * 0.8 });
                  };

                  document.getElementById('zoom-fit').onclick = function() {
                    network.fit();
                  };

                  // Set up copy to clipboard functionality
                  document.getElementById('copy-graph').onclick = function() {
                    try {
                      // Get the network container
                      const container = document.getElementById('network');
                      const canvas = container.querySelector('canvas');
                      
                      if (!canvas) {
                        console.error('Canvas not found');
                        showCopyError('Canvas not found');
                        return;
                      }
                      
                      // Check if canvas has content
                      if (canvas.width === 0 || canvas.height === 0) {
                        console.error('Canvas has no content');
                        showCopyError('Canvas has no content');
                        return;
                      }
                      
                      // Create a temporary canvas to capture the graph
                      const tempCanvas = document.createElement('canvas');
                      const ctx = tempCanvas.getContext('2d');
                      
                      // Set canvas size to match the network
                      tempCanvas.width = canvas.width;
                      tempCanvas.height = canvas.height;
                      
                      // Draw the network canvas onto the temporary canvas
                      ctx.drawImage(canvas, 0, 0);
                      
                      // Convert to blob and copy to clipboard
                      tempCanvas.toBlob(function(blob) {
                        if (!blob) {
                          console.error('Failed to create blob from canvas');
                          showCopyError('Failed to create image');
                          return;
                        }
                        
                        if (navigator.clipboard && navigator.clipboard.write) {
                          // Create clipboard item
                          const clipboardItem = new ClipboardItem({
                            'image/png': blob
                          });
                          
                          navigator.clipboard.write([clipboardItem]).then(function() {
                            // Show success message
                            const button = document.getElementById('copy-graph');
                            const originalText = button.innerHTML;
                            button.innerHTML = '✅';
                            button.style.background = '#10b981';
                            
                            setTimeout(function() {
                              button.innerHTML = originalText;
                              button.style.background = '#475569';
                            }, 2000);
                          }).catch(function(err) {
                            console.error('Failed to copy to clipboard:', err);
                            // Try fallback download instead
                            downloadImage(blob);
                          });
                        } else {
                          // Fallback for older browsers
                          downloadImage(blob);
                        }
                      }, 'image/png');
                    } catch (error) {
                      console.error('Error copying graph:', error);
                      showCopyError('Unexpected error: ' + error.message);
                    }
                  };
                  
                  function downloadImage(blob) {
                    try {
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'graph-visualization.png';
                      a.click();
                      URL.revokeObjectURL(url);
                      
                      // Show success message for download
                      const button = document.getElementById('copy-graph');
                      const originalText = button.innerHTML;
                      button.innerHTML = '💾';
                      button.style.background = '#10b981';
                      
                      setTimeout(function() {
                        button.innerHTML = originalText;
                        button.style.background = '#475569';
                      }, 2000);
                    } catch (error) {
                      console.error('Failed to download image:', error);
                      showCopyError('Download failed');
                    }
                  }
                  
                  function showCopyError(message = 'Copy failed') {
                    console.error('Copy error:', message);
                    const button = document.getElementById('copy-graph');
                    const originalText = button.innerHTML;
                    button.innerHTML = '❌';
                    button.style.background = '#ef4444';
                    
                    // Show error in console for debugging
                    console.error('Copy to clipboard failed:', message);
                    
                    setTimeout(function() {
                      button.innerHTML = originalText;
                      button.style.background = '#475569';
                    }, 2000);
                  }

                  // Handle edge hover events to show relationship properties
                  network.on('hoverEdge', function(params) {
                    const edge = edges.get(params.edge);
                    if (edge && edge.type === 'PARTICIPATES_IN') {
                      const tooltip = document.createElement('div');
                      tooltip.className = 'vis-tooltip';
                      tooltip.style.position = 'absolute';
                      tooltip.style.left = params.event.center.x + 10 + 'px';
                      tooltip.style.top = params.event.center.y + 10 + 'px';
                      tooltip.style.zIndex = '1000';
                      
                      let tooltipContent = '<strong>' + edge.type + '</strong><br>';
                      tooltipContent += 'Depth: ' + (edge.depth || 1) + '<br>';
                      if (edge.role) tooltipContent += 'Role: ' + edge.role + '<br>';
                      if (edge.ecContribution !== null && edge.ecContribution !== undefined) {
                        tooltipContent += 'EC Contribution: €' + edge.ecContribution.toLocaleString() + '<br>';
                      }
                      if (edge.totalCost !== null && edge.totalCost !== undefined) {
                        tooltipContent += 'Total Cost: €' + edge.totalCost.toLocaleString();
                      }
                      
                      tooltip.innerHTML = tooltipContent;
                      document.body.appendChild(tooltip);
                      
                      // Remove tooltip when mouse leaves
                      setTimeout(function() {
                        if (tooltip.parentNode) {
                          tooltip.parentNode.removeChild(tooltip);
                        }
                      }, 3000);
                    }
                  });

                  // Handle node click events
                  network.on('click', function(params) {
                    if (params.nodes.length > 0) {
                      const nodeId = params.nodes[0];
                      const node = nodes.get(nodeId);
                      const detailsPanel = document.getElementById('details-panel');
                      const nodeDetails = document.getElementById('node-details');
                      
                      // Show the details panel
                      detailsPanel.style.display = 'block';
                      
                      // Get connected edges
                      const connectedEdges = edges.get().filter(edge => 
                        edge.from === nodeId || edge.to === nodeId
                      );
                      
                      // Get connected nodes
                      const connectedNodes = connectedEdges.map(edge => {
                        const connectedId = edge.from === nodeId ? edge.to : edge.from;
                        return nodes.get(connectedId);
                      });
                      
                      // Update the details panel
                      const nodeDepth = node.depth !== undefined ? node.depth : 0;
                      
                      // Build enhanced node details based on type
                      // For root nodes, show the actual type, not the group (which is always 'Project' for coloring)
                      const displayType = nodeDepth === 0 ? (node.originalType || node.type || node.group) : node.group;
                      let nodeDetailsHTML = \`
                        <p><strong>Type:</strong> \${displayType}</p>
                        <p><strong>Label:</strong> \${node.label}</p>
                        <p><strong>ID:</strong> \${node.id}</p>
                        <p><strong>Depth:</strong> \${nodeDepth === 0 ? 'Root' : \`Level \${nodeDepth}\`}</p>
                      \`;
                      
                      // Add project-specific details
                      if (node.group === 'Project' && node.acronym) {
                        nodeDetailsHTML += \`<p><strong>Acronym:</strong> \${node.acronym}</p>\`;
                      }
                      
                      // Add organization-specific details
                      if (node.group === 'Organization' && node.country) {
                        nodeDetailsHTML += \`<p><strong>Organization:</strong> \${node.name || node.label} (\${node.country})</p>\`;
                      }
                      
                      nodeDetailsHTML += \`
                        <p><strong>Connected Nodes:</strong> \${connectedNodes.length}</p>
                      \`;
                      
                      nodeDetailsHTML += \`
                        <p><strong>Connections:</strong></p>
                        <ul>
                          \${connectedEdges.map(edge => {
                            const connectedNode = nodes.get(edge.to);
                            const sourceNode = nodes.get(edge.from);
                            const edgeDepth = edge.depth || 1;
                            
                            // For PARTICIPATES_IN relationships, show the appropriate node based on current node type
                            let displayNode = connectedNode;
                            if (edge.label === 'PARTICIPATES_IN') {
                              // PARTICIPATES_IN means "Organization participates in Project"
                              // Source = Organization, Target = Project
                              
                              // For root nodes, use the actual type, not the group (which is always 'Project' for coloring)
                              const currentNodeType = nodeDepth === 0 ? (node.originalType || node.type || node.group) : node.group;
                              
                              // If we're viewing an Organization node, show the Project (target node)
                              // If we're viewing a Project node, show the Organization (source node)
                              if (currentNodeType === 'Organization') {
                                displayNode = connectedNode; // Show the project (target)
                              } else {
                                displayNode = sourceNode; // Show the organization (source)
                              }
                            }
                            
                            let connectionInfo = \`<strong>\${edge.label}</strong> → \${displayNode.label} <span style="color: #6b7280; font-size: 0.9em;">(Depth \${edgeDepth})</span>\`;
                            
                            // Add relationship properties for PARTICIPATES_IN relationships
                            if (edge.label === 'PARTICIPATES_IN') {
                              const properties = [];
                              if (edge.role) properties.push(\`<strong>Role:</strong> \${edge.role}\`);
                              if (edge.ecContribution !== null && edge.ecContribution !== undefined) {
                                properties.push(\`<strong>EC Contribution:</strong> €\${edge.ecContribution.toLocaleString()}\`);
                              }
                              if (edge.totalCost !== null && edge.totalCost !== undefined) {
                                properties.push(\`<strong>Total Cost:</strong> €\${edge.totalCost.toLocaleString()}\`);
                              }
                              
                              if (properties.length > 0) {
                                connectionInfo += \`<br><small style="color: #94a3b8; margin-left: 10px;">\${properties.join(' | ')}</small>\`;
                              }
                            }
                            
                            return \`<li style="margin-bottom: 8px;">\${connectionInfo}</li>\`;
                          }).join('')}
                        </ul>
                      \`;
                      
                      nodeDetails.innerHTML = nodeDetailsHTML;
                    } else {
                      // Hide the details panel when clicking on empty space
                      document.getElementById('details-panel').style.display = 'none';
                    }
                  });
                }
              }

              // Set up level slider
              const levelSlider = document.getElementById('level-slider');
              const levelValue = document.getElementById('level-value');
              
              levelSlider.addEventListener('input', function() {
                const level = parseInt(this.value);
                const depthLabels = ['Root Only', 'Depth 1', 'Depth 2'];
                levelValue.textContent = depthLabels[level] || \`Depth \${level}\`;
                updateVisualization(level);
              });

              // Initial visualization
              updateVisualization(currentLevel);

            } catch (err) {
              console.error('Visualization error:', err);
              document.getElementById('error').textContent = 'Error creating visualization: ' + err.message;
              document.getElementById('error').style.display = 'block';
            }
          </script>
        </body>
        </html>
      `);
      visualizationWindow.document.close();
    } catch (err) {
      console.error('Visualization error:', err);
      if (err instanceof Error) {
        setError(err.message || 'Failed to visualize project');
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box
      bg={colors.cardBg}
      border="1px solid"
      borderColor={colors.cardBorder}
      borderRadius="xl"
      p={3}
      boxShadow={colors.shadow}
      className={className}
    >
      <VStack spacing={2} align="stretch">
        <Box>
          <Text 
            fontSize="lg" 
            fontWeight="bold" 
            mb={2} 
            color={colors.text}
            display="flex"
            alignItems="center"
            gap={2}
          >
            <FiTarget />
            Node Visualizer
          </Text>
        </Box>
        
        <VStack spacing={2} align="stretch">
          <Input
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="Enter Project ID, RCN, or Organization ID/name"
            bg={colors.inputBg}
            borderColor={colors.inputBorder}
            color={colors.text}
            _placeholder={{ color: colors.text + '60' }}
            borderRadius="lg"
            _hover={{
              borderColor: colors.primary,
            }}
            _focus={{
              borderColor: colors.primary,
              boxShadow: `0 0 0 1px ${colors.primary}30`,
            }}
          />
          <Button
            onClick={handleVisualize}
            disabled={isLoading || !nodeId.trim()}
            bg={isButtonHighlighted ? '#ff4444' : colors.gradient}
            color="white"
            borderRadius="lg"
            px={6}
            _hover={{
              bg: colors.gradientDark,
              transform: 'translateY(-1px)',
              boxShadow: colors.shadowLg,
            }}
            _active={{
              transform: 'translateY(0)',
            }}
            transition="all 0.2s ease-in-out"
            leftIcon={<FiShare2 />}
            isLoading={isLoading}
            loadingText="Loading..."
            boxShadow={isButtonHighlighted ? '0 0 20px rgba(255, 68, 68, 0.6)' : 'none'}
            animation={isButtonHighlighted ? 'pulse 1s ease-in-out' : 'none'}
          >
            Visualize
          </Button>
        </VStack>
        
        {error && (
          <Box 
            mt={2} 
            p={4} 
            bg="red.50" 
            border="1px solid" 
            borderColor="red.200" 
            borderRadius="lg"
            _dark={{
              bg: 'red.900',
              borderColor: 'red.700',
            }}
          >
            <Text fontSize="sm" color="red.600" display="flex" alignItems="center" gap={2}>
              <FiAlertCircle />
              {error}
            </Text>
          </Box>
        )}
      </VStack>
    </Box>
  );
};

export default NodeVisualizer; 