from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from sqlalchemy import inspect
from .models import ConnectionConfig
from .forms import ConnectionForm
from core.rag.llm_utils import load_llm, load_embeddings
from core.rag.db_utils import connect_db
from core.rag.retriever import build_retriever
from core.rag.rag_pipeline import RAGPipeline

# Create your views here.

@login_required
def connections_view(request):
    conns = request.user.connections.all()
    if request.method == 'POST':
        if 'select_conn' in request.POST:
            conn_id = request.POST['select_conn']
            request.session['connection_id'] = conn_id
            return redirect('dashboard')

        form = ConnectionForm(request.POST)
        if form.is_valid():
            conn = form.save(commit=False)
            conn.owner = request.user
            conn.save()
            request.session['connection_id'] = conn.id
            return redirect('dashboard')
    else:
        form = ConnectionForm()
    return render(request, 'core/connections.html', {'form': form, 'connections': conns})

@login_required
def dashboard_view(request):
    conn_id = request.session.get('connection_id')
    if not conn_id:
        return redirect('connections')
    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)
    # create connection string
    conn_str = f"{conn.db_type}+pyodbc://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database_name}?driver=ODBC+Driver+17+for+SQL+Server"
    # connection test
    try:
        engine = connect_db(conn_str)
        status = "Connected"
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception as e:
        status = f"Error: {e}"
        tables = []
    return render(request, 'core/dashboard.html', {
        'conn': conn,
        'status': status,
        'tables': tables,
    })

@login_required
def chat_view(request):
    conn_id = request.session.get('connection_id')
    if not conn_id:
        return redirect('connections')
    
    # recreating connection string and engine
    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)
    conn_str = (
        f"{conn.db_type}+pyodbc://{conn.username}:{conn.password}@"
        f"{conn.host}:{conn.port}/{conn.database_name}"
        f"?driver=ODBC+Driver+17+for+SQL+Server"
    )
    try:
        engine = connect_db(conn_str)
    except Exception as e:
        return redirect('dashboard')

    sql = None
    if request.method == 'POST':
        question = request.POST['question']
        llm = load_llm()
        embeddings = load_embeddings()
        retriever = build_retriever(engine, embeddings)
        pipeline = RAGPipeline(llm, retriever, engine)
        sql, rows = pipeline.run(question)
        return render(request, 'core/chat.html', {'response': rows, 'sql': sql})
    return render(request, 'core/chat.html')