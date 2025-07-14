"""
ChromaDB Vector Store Setup for Job Dataset
"""

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
import os
from typing import  Dict, Any

class JobVectorStore:
    def __init__(self, csv_path: str = None, collection_name: str = "job_dataset", 
                 model_name: str = "all-MiniLM-L6-v2", persist_directory: str = "./chroma_db"):
        """
        Initialize the Job Vector Store with ChromaDB and HuggingFace embeddings
        
        Args:
            csv_path: Path to the job dataset CSV file (optional if already populated)
            collection_name: Name for the ChromaDB collection
            model_name: HuggingFace model name for embeddings
            persist_directory: Directory to persist ChromaDB
        """
        self.csv_path = csv_path
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Initialize the embedding model
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer(model_name)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Job dataset with comprehensive job information"}
        )
        
        # Load dataset if provided
        if csv_path and os.path.exists(csv_path):
            print("Loading dataset...")
            self.df = pd.read_csv(csv_path)
            print(f"Dataset loaded: {len(self.df)} rows, {len(self.df.columns)} columns")
        else:
            self.df = None
            print("No dataset provided or file not found. Using existing ChromaDB collection.")
    
    def create_comprehensive_text(self, row: pd.Series) -> str:
        """
        Create a comprehensive text representation of each job posting
        combining all relevant fields for better semantic search
        """
        # Core job information
        core_info = []
        if pd.notna(row['Role']):
            core_info.append(f"Role: {row['Role']}")
        if pd.notna(row['skills']):
            core_info.append(f"Skills: {row['skills']}")
        if pd.notna(row['Job_Description']):
            core_info.append(f"Description: {row['Job_Description']}")
        if pd.notna(row['Responsibilities']):
            core_info.append(f"Responsibilities: {row['Responsibilities']}")
        
        # Employment type specific information
        employment_types = ['Part_Time', 'Full_Time', 'Contract', 'Intern', 'Temporary']
        employment_info = []
        
        for emp_type in employment_types:
            if pd.notna(row[f'{emp_type}_count']) and row[f'{emp_type}_count'] > 0:
                type_info = [f"{emp_type} positions available"]
                
                
                # Add salary range
                if pd.notna(row[f'{emp_type}_salary_range']):
                    type_info.append(f"Salary: {row[f'{emp_type}_salary_range']}")
                
                # Add qualifications
                if pd.notna(row[f'{emp_type}_qualifications']):
                    type_info.append(f"Qualifications: {row[f'{emp_type}_qualifications']}")
                
                # Add benefits
                if pd.notna(row[f'{emp_type}_benefits']):
                    type_info.append(f"Benefits: {row[f'{emp_type}_benefits']}")
                
                # Add companies
                if pd.notna(row[f'{emp_type}_companies']):
                    type_info.append(f"Companies: {row[f'{emp_type}_companies']}")
                
                # Add portals
                if pd.notna(row[f'{emp_type}_portals']):
                    type_info.append(f"Portals: {row[f'{emp_type}_portals']}")
                
                employment_info.append(f"{emp_type}: " + "; ".join(type_info))
        
        # Combine all information
        all_info = core_info + employment_info
        return " | ".join(all_info)
    
    def create_metadata(self, row: pd.Series) -> Dict[str, Any]:
        """
        Create comprehensive metadata for each job posting
        """
        metadata = {
            'role_id': str(row['role_id']),
            'role': str(row['Role']) if pd.notna(row['Role']) else "",
            'total_postings': int(row['total_postings']) if pd.notna(row['total_postings']) else 0,
            'unique_companies': int(row['unique_companies']) if pd.notna(row['unique_companies']) else 0,
            'unique_portals': int(row['unique_portals']) if pd.notna(row['unique_portals']) else 0,
        }
        
        # Add employment type counts
        employment_types = ['Part_Time', 'Full_Time', 'Contract', 'Intern', 'Temporary']
        for emp_type in employment_types:
            count_col = f'{emp_type}_count'
            if pd.notna(row[count_col]):
                metadata[f'{emp_type.lower()}_count'] = int(row[count_col])
            else:
                metadata[f'{emp_type.lower()}_count'] = 0
        
        # Add skills as a separate field for filtering
        if pd.notna(row['skills']):
            metadata['skills'] = str(row['skills'])
        
        # Add all other fields as strings for complete searchability
        for col in self.df.columns:
            if col not in ['role_id', 'Role', 'total_postings', 'unique_companies', 'unique_portals'] + [f'{et}_count' for et in employment_types]:
                if pd.notna(row[col]):
                    metadata[col.lower()] = str(row[col])
        
        return metadata
    
    def populate_vector_store(self, batch_size: int = 32, force_recreate: bool = False):
        """
        Populate the ChromaDB vector store with job data
        """
        if self.df is None:
            print("No dataset loaded. Cannot populate vector store.")
            return False
            
        print("Creating comprehensive text representations...")
        
        # Check if collection already has data
        if self.collection.count() > 0 and not force_recreate:
            print(f"Collection already contains {self.collection.count()} documents.")
            print("Use force_recreate=True to repopulate.")
            return True
        
        if force_recreate and self.collection.count() > 0:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Job dataset with comprehensive job information"}
            )
        
        # Prepare data for embedding
        documents = []
        metadatas = []
        ids = []
        
        for idx, row in self.df.iterrows():
            # Create comprehensive text
            doc_text = self.create_comprehensive_text(row)
            documents.append(doc_text)
            
            # Create metadata
            metadata = self.create_metadata(row)
            metadatas.append(metadata)
            
            # Create unique ID
            ids.append(f"job_{row['role_id']}")
        
        print(f"Processing {len(documents)} documents in batches of {batch_size}...")
        
        # Process in batches to avoid memory issues
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_metadata = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            
            print(f"Processing batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
            
            # Generate embeddings
            batch_embeddings = self.embedding_model.encode(batch_docs, convert_to_tensor=False)
            
            # Add to collection
            self.collection.add(
                documents=batch_docs,
                embeddings=batch_embeddings.tolist(),
                metadatas=batch_metadata,
                ids=batch_ids
            )
        
        print(f"Successfully populated vector store with {len(documents)} job postings!")
        print(f"Collection now contains {self.collection.count()} documents.")
        return True
    
    def search_jobs(self, query: str, n_results: int = 10, filters: Dict = None) -> Dict:
        """
        Search for jobs based on a query (could be resume content or job requirements)
        
        Args:
            query: Search query (resume content, skills, job requirements)
            n_results: Number of results to return
            filters: Optional filters for metadata
            
        Returns:
            Dictionary containing search results
        """
        # Generate embedding for query
        query_embedding = self.embedding_model.encode([query], convert_to_tensor=False)
        
        # Search in ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results,
            where=filters,
            include=["documents", "metadatas", "distances"]
        )
        
        if not results['ids'][0]:  # No results found
            return {
                'documents': [],
                'metadatas': [],
                'distances': [],
                'ids': []
            }
        
        return {
            'documents': results['documents'][0],
            'metadatas': results['metadatas'][0],
            'distances': results['distances'][0],
            'ids': results['ids'][0]
        }
    
    def get_all_job_info(self, resume_text: str, n_results: int = 15) -> Dict:
        """
        Get comprehensive job information for a given resume
        
        Args:
            resume_text: User's resume text
            n_results: Number of job matches to analyze
            
        Returns:
            Dictionary with comprehensive job information
        """
        # Get matching jobs
        search_results = self.search_jobs(resume_text, n_results)
        
        if not search_results['metadatas']:
            return {
                'matching_jobs': [],
                'roles': [],
                'skills': [],
                'companies': [],
                'portals': [],
                'benefits': [],
                'salary_ranges': [],
                'qualifications': [],
                'employment_types': {},
                'total_matches': 0
            }
        
        # Process results
        matching_jobs = []
        all_roles = set()
        all_skills = set()
        all_companies = set()
        all_portals = set()
        all_benefits = set()
        all_salary_ranges = set()
        all_qualifications = set()
        employment_types = {'full_time': 0, 'part_time': 0, 'contract': 0, 'intern': 0, 'temporary': 0}
        
        for i, (doc, metadata, distance) in enumerate(zip(search_results['documents'], search_results['metadatas'], search_results['distances'])):
            # Calculate relevance score
            relevance_score = 1 - distance
            
            # Add to matching jobs
            matching_jobs.append({
                'rank': i + 1,
                'role': metadata.get('role', ''),
                'role_id': metadata.get('role_id', ''),
                'relevance_score': round(relevance_score, 4),
                'total_postings': metadata.get('total_postings', 0),
                'skills': metadata.get('skills', ''),
                'summary': doc[:200] + "..." if len(doc) > 200 else doc
            })
            
            # Collect unique information
            if metadata.get('role'):
                all_roles.add(metadata['role'])
            if metadata.get('skills'):
                all_skills.update([skill.strip() for skill in metadata['skills'].split(',') if skill.strip()])
            
            # Collect employment type specific information
            for emp_type in ['part_time', 'full_time', 'contract', 'intern', 'temporary']:
                # Count
                count = metadata.get(f'{emp_type}_count', 0)
                if count > 0:
                    employment_types[emp_type] += count
                
                # Companies
                companies_field = f'{emp_type}_companies'
                if companies_field in metadata and metadata[companies_field]:
                    companies = [c.strip() for c in str(metadata[companies_field]).split(',') if c.strip()]
                    all_companies.update(companies)
                
                # Portals
                portals_field = f'{emp_type}_portals'
                if portals_field in metadata and metadata[portals_field]:
                    portals = [p.strip() for p in str(metadata[portals_field]).split(',') if p.strip()]
                    all_portals.update(portals)
                
                # Benefits
                benefits_field = f'{emp_type}_benefits'
                if benefits_field in metadata and metadata[benefits_field]:
                    benefits = [b.strip() for b in str(metadata[benefits_field]).split(',') if b.strip()]
                    all_benefits.update(benefits)
                
                # Salary ranges
                salary_field = f'{emp_type}_salary_range'
                if salary_field in metadata and metadata[salary_field]:
                    all_salary_ranges.add(str(metadata[salary_field]))
            
                
                # Qualifications
                qual_field = f'{emp_type}_qualifications'
                if qual_field in metadata and metadata[qual_field]:
                    qualifications = [q.strip() for q in str(metadata[qual_field]).split(',') if q.strip()]
                    all_qualifications.update(qualifications)
        
        return {
            'matching_jobs': matching_jobs,
            'roles': list(all_roles),
            'skills': list(all_skills),
            'companies': list(all_companies),
            'portals': list(all_portals),
            'benefits': list(all_benefits),
            'salary_ranges': list(all_salary_ranges),
            'qualifications': list(all_qualifications),
            'employment_types': employment_types,
            'total_matches': len(matching_jobs)
        }
    
    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the collection
        """
        return {
            'total_documents': self.collection.count(),
            'collection_name': self.collection_name,
            'persist_directory': self.persist_directory
        }

def initialize_job_vectorstore(csv_path: str = "new_job_dataset.csv", force_recreate: bool = False) -> JobVectorStore:
    """
    Initialize and populate the job vector store
    
    Args:
        csv_path: Path to the job dataset CSV
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        JobVectorStore instance
    """
    try:
        job_store = JobVectorStore(csv_path)
        
        # Check if we need to populate
        if job_store.collection.count() == 0 or force_recreate:
            if job_store.df is not None:
                success = job_store.populate_vector_store(force_recreate=force_recreate)
                if not success:
                    print("Failed to populate vector store")
                    return None
            else:
                print("No dataset provided and collection is empty")
                return None
        
        stats = job_store.get_collection_stats()
        print(f"Job vector store ready with {stats['total_documents']} documents")
        return job_store
        
    except Exception as e:
        print(f"Error initializing job vector store: {str(e)}")
        return None

if __name__ == "__main__":
    # Initialize the vector store
    job_store = initialize_job_vectorstore("new_job_dataset.csv")
    
    if job_store:
        print("Job vector store initialized successfully!")
        
        # Test search
        test_resume = "Software engineer with Python and React experience"
        results = job_store.get_all_job_info(test_resume, n_results=5)
        print(f"Found {results['total_matches']} matching jobs")
        print(f"Eligible roles: {results['roles'][:5]}")
    else:
        print("Failed to initialize job vector store")