from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence

from chroma_setup import JobVectorStore


class JobQueryProcessor:
    def __init__(self, job_vectorstore: JobVectorStore):
        self.job_vectorstore = job_vectorstore
        self.llm = None
        self.llm_chain = None
        self.prompt = None
        self.initialize_llm()

    def initialize_llm(self):
        """Initialize the LLM and LangChain components"""
        try:
            print("Initializing LLM...")

            # Initialize Groq LLM
            self.llm = ChatGroq(
                groq_api_key="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",
                model_name="llama3-70b-8192",
                temperature=0.7,
                max_tokens=1000
            )

            self.prompt = PromptTemplate(
                input_variables=["resume_text", "job_info", "query"],
                template="""
You are a job search assistant. Based on the user's resume and the job information provided, answer the user's query in a helpful and informative way.

User's Resume:
{resume_text}

Relevant Job Information:
{job_info}

User's Query: {query}

Please provide a comprehensive answer based on the job information and the user's background. Be specific and helpful.

Answer:"""
            )

            # Use the LangChain v0.2+ RunnableSequence pattern
            self.llm_chain: RunnableSequence = self.prompt | self.llm

            print("LLM initialized successfully!")

        except Exception as e:
            print(f"Error initializing LLM: {str(e)}")
            self.llm = None
            self.llm_chain = None

    def format_job_info(self, job_data: Dict) -> str:
        """Format job information for the LLM"""
        formatted_info = []

        if job_data.get('matching_jobs'):
            formatted_info.append("MATCHING JOBS:")
            for job in job_data['matching_jobs'][:5]:
                formatted_info.append(
                    f"- {job['role']} (Relevance: {job['relevance_score']}, Postings: {job['total_postings']})")
                if job.get('skills'):
                    formatted_info.append(f"  Skills: {job['skills'][:100]}...")

        if job_data.get('roles'):
            formatted_info.append(f"\nELIGIBLE ROLES: {', '.join(job_data['roles'][:10])}")
        if job_data.get('skills'):
            formatted_info.append(f"\nREQUIRED SKILLS: {', '.join(job_data['skills'][:15])}")
        if job_data.get('companies'):
            formatted_info.append(f"\nHIRING COMPANIES: {', '.join(job_data['companies'][:10])}")
        if job_data.get('portals'):
            formatted_info.append(f"\nJOB PORTALS: {', '.join(job_data['portals'][:10])}")
        if job_data.get('benefits'):
            formatted_info.append(f"\nCOMMON BENEFITS: {', '.join(job_data['benefits'][:10])}")
        if job_data.get('salary_ranges'):
            formatted_info.append(f"\nSALARY RANGES: {', '.join(job_data['salary_ranges'][:5])}")
        if job_data.get('experience_ranges'):
            formatted_info.append(f"\nEXPERIENCE RANGES: {', '.join(job_data['experience_ranges'][:5])}")

        if job_data.get('employment_types'):
            emp_types = []
            for emp_type, count in job_data['employment_types'].items():
                if count > 0:
                    emp_types.append(f"{emp_type.replace('_', ' ').title()}: {count}")
            if emp_types:
                formatted_info.append(f"\nEMPLOYMENT TYPES: {', '.join(emp_types)}")

        return "\n".join(formatted_info)

    def generate_fallback_response(self, query: str, job_data: Dict) -> str:
        """Rule-based fallback response"""
        query_lower = query.lower()

        if any(k in query_lower for k in ['role', 'position', 'job', 'eligible', 'apply']):
            if job_data.get('roles'):
                return f"Based on your resume, you are eligible for these roles: {', '.join(job_data['roles'][:10])}. " \
                       f"I found {job_data.get('total_matches', 0)} matching job opportunities."

        if any(k in query_lower for k in ['portal', 'website', 'apply', 'where']):
            if job_data.get('portals'):
                return f"You can apply for jobs on these portals: {', '.join(job_data['portals'][:10])}."

        if any(k in query_lower for k in ['benefit', 'perk', 'advantage']):
            if job_data.get('benefits'):
                return f"Common benefits offered for your profile include: {', '.join(job_data['benefits'][:10])}."

        if any(k in query_lower for k in ['salary', 'pay', 'wage', 'compensation']):
            if job_data.get('salary_ranges'):
                return f"Based on matching jobs, expected salary ranges are: {', '.join(job_data['salary_ranges'][:5])}."

        if any(k in query_lower for k in ['skill', 'requirement', 'qualification']):
            if job_data.get('skills'):
                return f"Key skills in demand for your profile: {', '.join(job_data['skills'][:15])}."

        if any(k in query_lower for k in ['company', 'employer', 'organization']):
            if job_data.get('companies'):
                return f"Companies hiring for your profile: {', '.join(job_data['companies'][:10])}."

        return f"I found {job_data.get('total_matches', 0)} matching opportunities for your profile. " \
               f"You're eligible for roles like: {', '.join(job_data.get('roles', [])[:5])}. " \
               f"Would you like specific information about roles, salaries, benefits, or job portals?"

    def process_query(self, query: str, resume_text: str) -> Dict[str, Any]:
        """Main query processing function"""
        try:
            job_data = self.job_vectorstore.get_all_job_info(resume_text, n_results=20)

            if job_data['total_matches'] == 0:
                return {
                    'success': False,
                    'message': 'No matching jobs found for your profile.',
                    'data': job_data
                }

            formatted_job_info = self.format_job_info(job_data)

            if self.llm_chain:
                try:
                    response = self.llm_chain.invoke({
                        "resume_text": resume_text[:1000],
                        "job_info": formatted_job_info[:1500],
                        "query": query
                    })

                    # Extract content from ChatGroq response
                    if hasattr(response, 'content'):
                        response_text = response.content.strip()
                    else:
                        response_text = str(response).strip()

                    if response_text.startswith("Answer:"):
                        response_text = response_text[7:].strip()

                    response = response_text

                except Exception as e:
                    print(f"LLM generation failed: {str(e)}")
                    response = self.generate_fallback_response(query, job_data)
            else:
                response = self.generate_fallback_response(query, job_data)

            return {
                'success': True,
                'response': response,
                'job_data': job_data,
                'total_matches': job_data['total_matches']
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing query: {str(e)}',
                'data': None
            }