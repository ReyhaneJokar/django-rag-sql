from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from sqlalchemy import inspect, Table, MetaData, select, insert, update, delete
from sqlalchemy.types import Date, DateTime
from .models import ConnectionConfig
from .forms import ConnectionForm
from core.rag.llm_utils import load_llm, load_embeddings
from core.rag.db_utils import connect_db
from core.rag.retriever import build_retriever
from core.rag.rag_pipeline import RAGPipeline

# Create your views here.

DIALECT_MAP = {
    'postgres':   'postgresql+psycopg2',         
    'sqlserver':  'mssql+pyodbc',
    'oracle':     'oracle+cx_oracle',          
}

def conn_str_for(conn):
    dialect = DIALECT_MAP.get(conn.db_type)
    if not dialect:
        raise ValueError(f"Unsupported DB type: {conn.db_type}")

    if conn.db_type == 'sqlserver':
        return (
            f"{dialect}://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database_name}"
            f"?driver=ODBC+Driver+17+for+SQL+Server"
        )
    else:
        return (
            f"{dialect}://{conn.username}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database_name}"
        )


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
    status = ''
    tables = []
    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)
    # connection test
    try:
        conn_str = conn_str_for(conn)
        engine = connect_db(conn_str)
        status = "Connected"
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception as e:
        status = f"Error: {e}"
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
    if not conn_id:
        return redirect('connections')

    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)

    try:
        conn_str = conn_str_for(conn)
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


# ---------------------- CRUD OPERATIONS ON DATABASE -------------------

def get_engine_from_session(request):
    conn_id = request.session.get('connection_id')
    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)
    engine = connect_db(conn_str_for(conn))
    return engine

@login_required
def table_list(request, table_name):
    engine = get_engine_from_session(request)
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        result = conn.execute(select(table)).mappings().all()

    columns = table.columns.keys()
    rows_data = [
        [row[col] for col in columns]
        for row in result
    ]
    return render(request, 'core/table_list.html', {
        'table_name': table_name,
        'columns': columns,
        'rows': rows_data,
    })

@login_required
def table_add(request, table_name):
    engine = get_engine_from_session(request)
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    fields = []
    for col in table.columns:
        is_date = isinstance(col.type, (Date, DateTime))
        fields.append((col.name, '', is_date))

    if request.method == 'POST':
        data = {col: request.POST.get(col) for col, _, _ in fields}
        with engine.connect() as conn:
            conn.execute(insert(table).values(**data))
            conn.commit()
        return redirect('table_list', table_name=table_name)

    return render(request, 'core/table_form.html', {
        'table_name': table_name,
        'fields':      fields,
        'is_edit':    False,
        'pk':         None,
    })

@login_required
def table_edit(request, table_name, pk):
    engine = get_engine_from_session(request)
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    key_col = list(table.primary_key.columns)[0].name

    with engine.connect() as conn:
        existing = conn.execute(
            select(table).where(table.c[key_col] == pk)
        ).mappings().first()

    fields = []
    for col in table.columns:
        value = existing.get(col.name, '')
        if isinstance(value, (Date, DateTime)):
            value = value.isoformat()
        is_date = isinstance(col.type, (Date, DateTime))
        fields.append((col.name, value, is_date))


    if request.method == 'POST':
        data = {col: request.POST.get(col) for col, _, _ in fields}
        with engine.connect() as conn:
            conn.execute(
                update(table).where(table.c[key_col] == pk).values(**data)
            )
            conn.commit()
        return redirect('table_list', table_name=table_name)

    return render(request, 'core/table_form.html', {
        'table_name': table_name,
        'fields':      fields,
        'is_edit':     True,
        'pk':          pk,
    })

@login_required
def table_delete(request, table_name, pk):
    engine = get_engine_from_session(request)
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    key_col = list(table.primary_key.columns)[0].name

    if request.method == 'POST':
        with engine.connect() as conn:
            conn.execute(
                delete(table).where(table.c[key_col] == pk)
            )
            conn.commit()
        return redirect('table_list', table_name=table_name)

    return render(request, 'core/table_confirm_delete.html', {
        'table_name': table_name,
        'pk': pk,
    })