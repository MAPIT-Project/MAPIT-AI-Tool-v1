#!/usr/bin/env python3
"""
Improved Ultra-Safe Semantic Graph Neural Network Training Script

This version uses sentence transformers for proper semantic embeddings while maintaining ultra-safety.
Key improvements:
1. Uses sentence transformers for text encoding
2. Maintains ultra-safety (CPU-only, no multiprocessing)
3. Proper semantic similarity training
4. Better embedding quality
"""

import os
from dotenv import load_dotenv
load_dotenv()
import sys
import json
import pickle
import logging
import warnings
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from tqdm import tqdm

# Disable all warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import sentence-transformers with multiprocessing disabled
try:
    import os
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    from sentence_transformers import SentenceTransformer
    logger.info("Loaded sentence-transformers with multiprocessing disabled")
except ImportError:
    SentenceTransformer = None
    logger.warning("sentence-transformers not available")

class ImprovedUltraSafeSemanticConfig:
    """Improved ultra-safe configuration with sentence transformers"""
    
    # Neo4j connection
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
    
    # Model parameters - optimized for semantic understanding
    EMBEDDING_DIM = 384  # Match sentence transformer dimension
    HIDDEN_DIM = 512     # Larger hidden dimension
    NUM_LAYERS = 4       # More layers for better representation
    DROPOUT = 0.2
    LEARNING_RATE = 0.001
    NUM_EPOCHS = 150     # More epochs for better training
    BATCH_SIZE = 32
    
    # Training parameters
    TRAIN_RATIO = 0.8
    VAL_RATIO = 0.1
    TEST_RATIO = 0.1
    
    # Semantic training parameters
    USE_SEMANTIC_TRAINING = True
    SEMANTIC_LOSS_WEIGHT = 0.5  # Higher weight for semantic similarity
    TEXT_ENCODER_MODEL = "all-MiniLM-L6-v2"
    
    # File paths
    SCHEMA_PATH = "neo4j_schema.json"
    OUTPUT_DIR = "improved_ultra_safe_semantic_graph_nn_output"
    MODEL_PATH = "improved_ultra_safe_semantic_graph_nn_model.pth"
    ENCODERS_PATH = "improved_ultra_safe_semantic_encoders.pkl"
    
    # Checkpoint paths
    CHECKPOINT_DIR = "improved_ultra_safe_semantic_checkpoints"
    PROCESSED_DATA_PATH = "improved_ultra_safe_semantic_processed_data.pkl"
    
    # Node types to exclude from training (optional)
    EXCLUDE_NODE_TYPES = set()  # Add node types to exclude if needed
    
    # Properties to exclude (embedding-related)
    EXCLUDE_PROPERTIES = {
        'embedding', 'graphEmbedding', 'GNNEmbedding', 'titleObjectiveEmbedding', 
        'titleDescriptionEmbedding', 'SafeSemanticGNNEmbedding'
    }
    
    # Text properties to use for semantic encoding
    TEXT_PROPERTIES = {
        'title', 'name', 'description', 'objective', 'summary', 'abstract'
    }
    
    # ULTRA SAFETY SETTINGS
    USE_CPU_ONLY = True  # Force CPU-only mode
    DISABLE_ALL_PARALLEL = True
    MAX_TEXT_LENGTH = 512  # Increased for better semantic capture

class ImprovedUltraSafeSemanticGraphNeuralNetwork(nn.Module):
    """Improved ultra-safe semantic GNN with sentence transformer integration"""
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, num_layers: int, dropout: float = 0.2):
        super(ImprovedUltraSafeSemanticGraphNeuralNetwork, self).__init__()
        
        self.num_layers = num_layers
        self.dropout = dropout
        
        # Input layer
        self.input_layer = nn.Linear(input_dim, hidden_dim)
        
        # Hidden layers (Graph Convolutional layers)
        self.conv_layers = nn.ModuleList()
        for _ in range(num_layers - 1):
            self.conv_layers.append(GCNConv(hidden_dim, hidden_dim))
        
        # Output layer
        self.output_layer = nn.Linear(hidden_dim, output_dim)
        
        # Batch normalization layers
        self.batch_norms = nn.ModuleList()
        for _ in range(num_layers - 1):
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim))
        
        # Dropout layer
        self.dropout_layer = nn.Dropout(dropout)
        
        # Text encoder for semantic understanding
        self.text_encoder = None
        if ImprovedUltraSafeSemanticConfig.USE_SEMANTIC_TRAINING and SentenceTransformer is not None:
            try:
                self.text_encoder = SentenceTransformer(ImprovedUltraSafeSemanticConfig.TEXT_ENCODER_MODEL)
                logger.info(f"Loaded text encoder: {ImprovedUltraSafeSemanticConfig.TEXT_ENCODER_MODEL}")
            except Exception as e:
                logger.warning(f"Failed to load text encoder: {e}")
        
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """Forward pass through the GNN"""
        # Input layer
        x = F.relu(self.input_layer(x))
        x = self.dropout_layer(x)
        
        # Hidden layers with graph convolutions
        for i in range(self.num_layers - 1):
            x = self.conv_layers[i](x, edge_index)
            x = self.batch_norms[i](x)
            x = F.relu(x)
            x = self.dropout_layer(x)
        
        # Output layer
        embeddings = self.output_layer(x)
        
        return embeddings
    
    def encode_text(self, text: str) -> torch.Tensor:
        """Encode text using the sentence transformer"""
        if self.text_encoder is None:
            raise ValueError("Text encoder not available")
        
        with torch.no_grad():
            embedding = self.text_encoder.encode(text)
            return torch.tensor(embedding, dtype=torch.float)

def extract_text_for_node(node_data: Dict[str, Any]) -> str:
    """Extract text from node data for semantic encoding"""
    text_parts = []
    
    for prop in ImprovedUltraSafeSemanticConfig.TEXT_PROPERTIES:
        if prop in node_data and node_data[prop]:
            value = str(node_data[prop]).strip()
            if value and value.lower() not in ['null', 'none', 'nan']:
                text_parts.append(value)
    
    return " ".join(text_parts)

def compute_semantic_loss(gnn_embeddings: torch.Tensor, text_embeddings: torch.Tensor) -> torch.Tensor:
    """Compute semantic similarity loss between GNN embeddings and text embeddings"""
    if text_embeddings is None or gnn_embeddings.shape != text_embeddings.shape:
        return torch.tensor(0.0, device=gnn_embeddings.device)
    
    # Compute cosine similarity loss
    # Normalize embeddings
    gnn_norm = F.normalize(gnn_embeddings, p=2, dim=1)
    text_norm = F.normalize(text_embeddings, p=2, dim=1)
    
    # Compute cosine similarity
    similarity = torch.sum(gnn_norm * text_norm, dim=1)
    
    # Loss: maximize similarity (minimize negative similarity)
    loss = -torch.mean(similarity)
    
    return loss

def load_schema() -> Dict[str, Any]:
    """Load Neo4j schema"""
    try:
        with open(ImprovedUltraSafeSemanticConfig.SCHEMA_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Schema file not found: {ImprovedUltraSafeSemanticConfig.SCHEMA_PATH}")
        return {}

def connect_to_neo4j():
    """Connect to Neo4j database"""
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(
            ImprovedUltraSafeSemanticConfig.NEO4J_URI,
            auth=(ImprovedUltraSafeSemanticConfig.NEO4J_USER, ImprovedUltraSafeSemanticConfig.NEO4J_PASSWORD)
        )
        
        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()['test']
            if test_value == 1:
                logger.info("Successfully connected to Neo4j")
                return driver
            else:
                raise Exception("Neo4j connection test failed")
                
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise

def get_node_properties_by_label(schema: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Get node properties by label from schema"""
    node_properties = {}
    
    if 'nodeLabels' in schema:
        for label_info in schema['nodeLabels']:
            label = label_info['name']
            properties = set()
            
            if 'properties' in label_info:
                for prop in label_info['properties']:
                    prop_name = prop['name']
                    if prop_name not in ImprovedUltraSafeSemanticConfig.EXCLUDE_PROPERTIES:
                        properties.add(prop_name)
            
            if properties:
                node_properties[label] = properties
    
    return node_properties

def extract_nodes_data(driver, node_properties: Dict[str, Set[str]]) -> Dict[str, List[Dict[str, Any]]]:
    """Extract nodes data from Neo4j (ultra-safe version)"""
    logger.info("Extracting nodes data (ultra-safe mode)...")
    
    nodes_data = {}
    
    with driver.session() as session:
        for label, properties in tqdm(node_properties.items(), desc="Extracting nodes by type"):
            if label in ImprovedUltraSafeSemanticConfig.EXCLUDE_NODE_TYPES:
                continue
                
            # Build Cypher query
            property_list = ', '.join([f'n.{prop} as {prop}' for prop in properties])
            query = f"""
            MATCH (n:{label})
            RETURN id(n) as node_id, {property_list}
            """
            
            try:
                result = session.run(query)
                nodes = []
                
                for record in result:
                    node_data = {'node_id': record['node_id']}
                    for prop in properties:
                        node_data[prop] = record[prop]
                    nodes.append(node_data)
                
                if nodes:
                    nodes_data[label] = nodes
                    logger.info(f"Extracted {len(nodes)} nodes of type {label}")
                    
            except Exception as e:
                logger.warning(f"Failed to extract nodes for {label}: {e}")
                continue
    
    return nodes_data

def extract_edges_data(driver) -> List[Dict[str, Any]]:
    """Extract edges data from Neo4j"""
    logger.info("Extracting edges data...")
    
    with driver.session() as session:
        query = """
        MATCH (a)-[r]->(b)
        RETURN id(a) as source_id, id(b) as target_id, type(r) as relationship_type
        """
        
        result = session.run(query)
        edges = []
        
        for record in result:
            edges.append({
                'source_id': record['source_id'],
                'target_id': record['target_id'],
                'relationship_type': record['relationship_type']
            })
        
        logger.info(f"Extracted {len(edges)} edges")
        return edges

def extract_graph_data(driver, schema: Dict[str, Any]) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Extract graph data from Neo4j"""
    logger.info("Extracting graph data...")
    
    # Get node properties by label
    node_properties = get_node_properties_by_label(schema)
    
    # Extract nodes and edges
    nodes_data = extract_nodes_data(driver, node_properties)
    edges_data = extract_edges_data(driver)
    
    return nodes_data, edges_data

def create_node_id_mapping(nodes_data: Dict[str, List[Dict[str, Any]]]) -> Dict[int, int]:
    """Create mapping from Neo4j node IDs to sequential indices"""
    node_id_mapping = {}
    current_idx = 0
    
    for label, nodes in nodes_data.items():
        for node in nodes:
            neo4j_id = node['node_id']
            node_id_mapping[neo4j_id] = current_idx
            current_idx += 1
    
    logger.info(f"Created node ID mapping for {len(node_id_mapping)} nodes")
    return node_id_mapping

def process_node_features_with_semantic(nodes_data: Dict[str, List[Dict[str, Any]]], 
                                      node_id_mapping: Dict[int, int],
                                      text_encoder) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Process node features with semantic text encoding (ultra-safe version)"""
    logger.info("Processing node features with semantic encoding (ultra-safe mode)...")
    
    total_nodes = sum(len(nodes) for nodes in nodes_data.values())
    feature_dim = ImprovedUltraSafeSemanticConfig.EMBEDDING_DIM
    
    # Initialize feature tensor
    node_features = torch.zeros(total_nodes, feature_dim)
    
    # Process each node type
    feature_encoders = {}
    
    for label, nodes in tqdm(nodes_data.items(), desc="Processing node types"):
        logger.info(f"Processing {len(nodes)} nodes of type {label}")
        
        for node in nodes:
            neo4j_id = node['node_id']
            if neo4j_id not in node_id_mapping:
                continue
            
            idx = node_id_mapping[neo4j_id]
            
            # Extract text for semantic encoding
            text = extract_text_for_node(node)
            
            if text and text_encoder:
                try:
                    # Encode text using sentence transformer
                    text_embedding = text_encoder.encode(text)
                    node_features[idx] = torch.tensor(text_embedding, dtype=torch.float)
                except Exception as e:
                    logger.warning(f"Failed to encode text for node {neo4j_id}: {e}")
                    # Use random initialization as fallback
                    node_features[idx] = torch.randn(feature_dim) * 0.1
            else:
                # Use random initialization for nodes without text
                node_features[idx] = torch.randn(feature_dim) * 0.1
    
    logger.info(f"Processed node features with shape: {node_features.shape}")
    return node_features, feature_encoders

def process_edge_indices(edges_data: List[Dict[str, Any]], node_id_mapping: Dict[int, int]) -> torch.Tensor:
    """Process edge indices"""
    logger.info("Processing edge indices...")
    
    edge_list = []
    
    for edge in edges_data:
        source_id = edge['source_id']
        target_id = edge['target_id']
        
        if source_id in node_id_mapping and target_id in node_id_mapping:
            source_idx = node_id_mapping[source_id]
            target_idx = node_id_mapping[target_id]
            edge_list.append([source_idx, target_idx])
            # Add reverse edge for undirected graph
            edge_list.append([target_idx, source_idx])
    
    if edge_list:
        edge_indices = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        logger.info(f"Processed edge indices with shape: {edge_indices.shape}")
        return edge_indices
    else:
        logger.warning("No valid edges found")
        return torch.empty((2, 0), dtype=torch.long)

def create_graph_data(node_features: torch.Tensor, edge_indices: torch.Tensor, 
                     node_id_mapping: Dict[int, int]) -> Data:
    """Create PyTorch Geometric Data object"""
    logger.info("Creating graph data...")
    
    graph_data = Data(
        x=node_features,
        edge_index=edge_indices,
        num_nodes=len(node_id_mapping)
    )
    
    logger.info(f"Created graph data with {graph_data.num_nodes} nodes and {graph_data.edge_index.shape[1]} edges")
    return graph_data

def save_checkpoint(data: Dict[str, Any], checkpoint_path: str):
    """Save checkpoint data"""
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    with open(checkpoint_path, 'wb') as f:
        pickle.dump(data, f)
    logger.info(f"Saved checkpoint to {checkpoint_path}")

def load_checkpoint(checkpoint_path: str) -> Optional[Dict[str, Any]]:
    """Load checkpoint data"""
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'rb') as f:
            data = pickle.load(f)
        logger.info(f"Loaded checkpoint from {checkpoint_path}")
        return data
    return None

def preprocess_data(nodes_data: Dict[str, List[Dict[str, Any]]], edges_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Preprocess data for training (ultra-safe version)"""
    logger.info("Preprocessing data (ultra-safe mode)...")
    
    # Create node ID mapping
    node_id_mapping = create_node_id_mapping(nodes_data)
    
    # Load text encoder
    text_encoder = None
    if ImprovedUltraSafeSemanticConfig.USE_SEMANTIC_TRAINING and SentenceTransformer is not None:
        try:
            text_encoder = SentenceTransformer(ImprovedUltraSafeSemanticConfig.TEXT_ENCODER_MODEL)
            logger.info(f"Loaded text encoder: {ImprovedUltraSafeSemanticConfig.TEXT_ENCODER_MODEL}")
        except Exception as e:
            logger.warning(f"Failed to load text encoder: {e}")
    
    # Process node features with semantic encoding
    node_features, feature_encoders = process_node_features_with_semantic(nodes_data, node_id_mapping, text_encoder)
    
    # Process edge indices
    edge_indices = process_edge_indices(edges_data, node_id_mapping)
    
    # Create graph data
    graph_data = create_graph_data(node_features, edge_indices, node_id_mapping)
    
    # Prepare processed data
    processed_data = {
        'graph_data': graph_data,
        'node_id_mapping': node_id_mapping,
        'nodes_data': nodes_data,
        'feature_encoders': feature_encoders,
        'text_encoder': text_encoder
    }
    
    # Save checkpoint
    checkpoint_path = os.path.join(ImprovedUltraSafeSemanticConfig.CHECKPOINT_DIR, ImprovedUltraSafeSemanticConfig.PROCESSED_DATA_PATH)
    save_checkpoint(processed_data, checkpoint_path)
    
    return processed_data

def compute_reconstruction_loss(embeddings: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
    """Compute graph reconstruction loss"""
    # Normalize embeddings
    embeddings_norm = F.normalize(embeddings, p=2, dim=1)
    
    # Compute similarity matrix
    similarity_matrix = torch.mm(embeddings_norm, embeddings_norm.t())
    
    # Create adjacency matrix from edge_index
    num_nodes = embeddings.shape[0]
    adjacency_matrix = torch.zeros(num_nodes, num_nodes, device=embeddings.device)
    adjacency_matrix[edge_index[0], edge_index[1]] = 1.0
    
    # Compute reconstruction loss
    loss = F.binary_cross_entropy_with_logits(similarity_matrix, adjacency_matrix)
    
    return loss

def train_improved_ultra_safe_semantic_model(processed_data: Dict[str, Any]) -> Tuple[ImprovedUltraSafeSemanticGraphNeuralNetwork, Dict[str, Any]]:
    """Train the improved ultra-safe semantic model"""
    logger.info("Training improved ultra-safe semantic model...")
    
    graph_data = processed_data['graph_data']
    text_encoder = processed_data.get('text_encoder')
    
    # Initialize model
    model = ImprovedUltraSafeSemanticGraphNeuralNetwork(
        input_dim=graph_data.x.shape[1],
        hidden_dim=ImprovedUltraSafeSemanticConfig.HIDDEN_DIM,
        output_dim=ImprovedUltraSafeSemanticConfig.EMBEDDING_DIM,
        num_layers=ImprovedUltraSafeSemanticConfig.NUM_LAYERS,
        dropout=ImprovedUltraSafeSemanticConfig.DROPOUT
    )
    
    # Move to CPU for ultra-safety
    device = torch.device('cpu')
    model = model.to(device)
    graph_data = graph_data.to(device)
    
    # Initialize optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=ImprovedUltraSafeSemanticConfig.LEARNING_RATE)
    
    # Training loop
    model.train()
    train_losses = []
    semantic_losses = []
    
    logger.info(f"Starting training for {ImprovedUltraSafeSemanticConfig.NUM_EPOCHS} epochs...")
    
    for epoch in tqdm(range(ImprovedUltraSafeSemanticConfig.NUM_EPOCHS), desc="Training"):
        optimizer.zero_grad()
        
        # Forward pass
        embeddings = model(graph_data.x, graph_data.edge_index)
        
        # Compute graph reconstruction loss
        graph_loss = compute_reconstruction_loss(embeddings, graph_data.edge_index)
        
        # Compute semantic loss if text encoder is available
        semantic_loss = torch.tensor(0.0, device=device)
        if text_encoder and ImprovedUltraSafeSemanticConfig.USE_SEMANTIC_TRAINING:
            try:
                # Generate text embeddings for comparison
                text_embeddings = []
                for node_data in processed_data['nodes_data'].values():
                    for node in node_data:
                        text = extract_text_for_node(node)
                        if text:
                            text_emb = text_encoder.encode(text)
                            text_embeddings.append(text_emb)
                
                if text_embeddings:
                    text_embeddings_tensor = torch.tensor(text_embeddings, device=device)
                    # Pad or truncate to match GNN embeddings
                    if text_embeddings_tensor.shape[0] < embeddings.shape[0]:
                        padding = torch.zeros(embeddings.shape[0] - text_embeddings_tensor.shape[0], 
                                            text_embeddings_tensor.shape[1], device=device)
                        text_embeddings_tensor = torch.cat([text_embeddings_tensor, padding], dim=0)
                    elif text_embeddings_tensor.shape[0] > embeddings.shape[0]:
                        text_embeddings_tensor = text_embeddings_tensor[:embeddings.shape[0]]
                    
                    semantic_loss = compute_semantic_loss(embeddings, text_embeddings_tensor)
            except Exception as e:
                logger.warning(f"Failed to compute semantic loss: {e}")
        
        # Combined loss
        total_loss = graph_loss + ImprovedUltraSafeSemanticConfig.SEMANTIC_LOSS_WEIGHT * semantic_loss
        
        # Backward pass
        total_loss.backward()
        optimizer.step()
        
        train_losses.append(graph_loss.item())
        semantic_losses.append(semantic_loss.item())
        
        if epoch % 20 == 0:
            logger.info(f"Epoch {epoch}: Graph Loss = {graph_loss.item():.4f}, Semantic Loss = {semantic_loss.item():.4f}")
    
    logger.info("Training completed!")
    
    return model, processed_data['feature_encoders']

def generate_improved_ultra_safe_embeddings(model: ImprovedUltraSafeSemanticGraphNeuralNetwork, processed_data: Dict[str, Any], driver, encoders: Dict[str, Any]):
    """Generate improved ultra-safe embeddings"""
    logger.info("Generating improved ultra-safe embeddings...")
    
    graph_data = processed_data['graph_data']
    node_id_mapping = processed_data['node_id_mapping']
    nodes_data = processed_data['nodes_data']
    
    # Move to CPU for ultra-safety
    device = torch.device('cpu')
    model = model.to(device)
    graph_data = graph_data.to(device)
    
    # Generate embeddings
    model.eval()
    with torch.no_grad():
        embeddings = model(graph_data.x, graph_data.edge_index)
    
    # Convert to numpy
    embeddings_np = embeddings.cpu().numpy()
    
    logger.info(f"Generated embeddings with shape: {embeddings_np.shape}")
    
    # Save embeddings to Neo4j
    save_improved_ultra_safe_embeddings_to_neo4j(driver, embeddings_np, node_id_mapping, nodes_data)
    
    # Save model and encoders
    save_improved_ultra_safe_model_and_encoders(model, encoders)
    
    # Generate statistics
    generate_improved_ultra_safe_embedding_statistics(embeddings_np, nodes_data)
    
    logger.info("Improved ultra-safe embedding generation completed!")

def save_improved_ultra_safe_embeddings_to_neo4j(driver, embeddings: np.ndarray, node_id_mapping: Dict[int, int], nodes_data: Dict[str, List[Dict[str, Any]]]):
    """Save generated improved ultra-safe embeddings back to Neo4j"""
    logger.info("Saving improved ultra-safe embeddings to Neo4j...")
    
    # Create reverse mapping
    reverse_mapping = {v: k for k, v in node_id_mapping.items()}
    
    with driver.session() as session:
        # Process nodes by type for efficiency
        for label, nodes in tqdm(nodes_data.items(), desc="Saving improved ultra-safe embeddings by type"):
            if not nodes:
                continue
            
            # Prepare batch update
            batch_size = 1000
            total_batches = (len(nodes) + batch_size - 1) // batch_size
            
            for i in tqdm(range(0, len(nodes), batch_size), desc=f"Processing {label} batches", leave=False):
                batch = nodes[i:i + batch_size]
                
                # Create Cypher query for batch update
                batch_nodes = []
                batch_embeddings = []
                
                for node in batch:
                    neo4j_id = node['node_id']
                    if neo4j_id in reverse_mapping:
                        embedding_idx = reverse_mapping[neo4j_id]
                        
                        if embedding_idx >= embeddings.shape[0]:
                            logger.error(f"Index out of bounds: neo4j_id={neo4j_id}, embedding_idx={embedding_idx}")
                            continue
                        
                        embedding = embeddings[embedding_idx].tolist()
                        batch_nodes.append(neo4j_id)
                        batch_embeddings.append(embedding)
                
                if batch_nodes:
                    # Use UNWIND with range to process nodes and embeddings together
                    query = """
                    UNWIND range(0, size($nodes) - 1) AS idx
                    WITH idx, $nodes[idx] AS node_id, $embeddings[idx] AS embedding
                    MATCH (n) WHERE id(n) = node_id
                    SET n.GNNEmbedding = embedding
                    """
                    
                    params = {
                        'nodes': batch_nodes,
                        'embeddings': batch_embeddings
                    }
                    
                    try:
                        result = session.run(query, params)
                        logger.debug(f"Updated {len(batch_nodes)} nodes in batch {i//batch_size} for {label}")
                    except Exception as e:
                        logger.warning(f"Error updating batch {i//batch_size} for {label}: {e}")
                        continue
    
    # Verify that embeddings were actually saved
    logger.info("Verifying improved ultra-safe embeddings were saved...")
    with driver.session() as session:
        count_query = "MATCH (n) WHERE n.GNNEmbedding IS NOT NULL RETURN count(n) AS count"
        result = session.run(count_query)
        count = result.single()['count']
        logger.info(f"Found {count} nodes with GNNEmbedding property")

def save_improved_ultra_safe_model_and_encoders(model: ImprovedUltraSafeSemanticGraphNeuralNetwork, encoders: Dict[str, Any]):
    """Save the trained improved ultra-safe model and encoders"""
    logger.info("Saving improved ultra-safe model and encoders...")
    
    # Create output directory
    os.makedirs(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, exist_ok=True)
    
    # Save model
    model_path = os.path.join(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, ImprovedUltraSafeSemanticConfig.MODEL_PATH)
    torch.save(model.state_dict(), model_path)
    
    # Save encoders
    encoders_path = os.path.join(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, ImprovedUltraSafeSemanticConfig.ENCODERS_PATH)
    with open(encoders_path, 'wb') as f:
        pickle.dump(encoders, f)
    
    logger.info(f"Improved ultra-safe model saved to {model_path}")
    logger.info(f"Improved ultra-safe encoders saved to {encoders_path}")

def generate_improved_ultra_safe_embedding_statistics(embeddings: np.ndarray, nodes_data: Dict[str, List[Dict[str, Any]]]):
    """Generate and save improved ultra-safe embedding statistics"""
    logger.info("Generating improved ultra-safe embedding statistics...")
    
    # Create output directory
    os.makedirs(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, exist_ok=True)
    
    # Basic statistics
    stats = {
        'total_nodes': embeddings.shape[0],
        'embedding_dimension': embeddings.shape[1],
        'mean_norm': float(np.mean(np.linalg.norm(embeddings, axis=1))),
        'std_norm': float(np.std(np.linalg.norm(embeddings, axis=1))),
        'min_norm': float(np.min(np.linalg.norm(embeddings, axis=1))),
        'max_norm': float(np.max(np.linalg.norm(embeddings, axis=1))),
        'node_type_counts': {}
    }
    
    # Count nodes by type
    for label, nodes in nodes_data.items():
        stats['node_type_counts'][label] = len(nodes)
    
    # Save statistics
    stats_path = os.path.join(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, 'improved_ultra_safe_embedding_statistics.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    logger.info(f"Improved ultra-safe embedding statistics saved to {stats_path}")

def main():
    """Main improved ultra-safe semantic training pipeline"""
    logger.info("Starting Improved Ultra-Safe Semantic Graph Neural Network training pipeline")
    logger.info("This version uses sentence transformers for proper semantic embeddings")
    
    # Create output directory
    os.makedirs(ImprovedUltraSafeSemanticConfig.OUTPUT_DIR, exist_ok=True)
    os.makedirs(ImprovedUltraSafeSemanticConfig.CHECKPOINT_DIR, exist_ok=True)
    
    # Step 1: Load schema and connect to Neo4j
    logger.info("Step 1: Loading schema and connecting to Neo4j")
    schema = load_schema()
    driver = connect_to_neo4j()
    
    try:
        # Step 2: Extract and preprocess data
        logger.info("Step 2: Extracting and preprocessing graph data")
        nodes_data, edges_data = extract_graph_data(driver, schema)
        processed_data = preprocess_data(nodes_data, edges_data)
        
        # Step 3: Train improved ultra-safe semantic model
        logger.info("Step 3: Training improved ultra-safe semantic model")
        model, encoders = train_improved_ultra_safe_semantic_model(processed_data)
        
        # Step 4: Generate embeddings and save results
        logger.info("Step 4: Generating embeddings and saving results")
        generate_improved_ultra_safe_embeddings(model, processed_data, driver, encoders)
        
        logger.info("Improved ultra-safe semantic training pipeline completed successfully!")
        
    finally:
        driver.close()

if __name__ == "__main__":
    main() 