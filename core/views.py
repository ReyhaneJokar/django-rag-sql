from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from sqlalchemy import inspect, Table, MetaData, select, insert, update, delete
from sqlalchemy.types import Date, DateTime
import openai
from django.conf import settings
from .models import ConnectionConfig
from .forms import ConnectionForm, AudioQueryForm
from core.rag.llm_utils import load_llm, load_embeddings
from core.rag.db_utils import connect_db
from core.rag.retriever import build_retriever
from core.rag.rag_pipeline import RAGPipeline

# Create your views here.

openai.api_key = settings.OPENAI_API_KEY

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
    sql = None
    rows = None
    error = None
    transcript= None
    is_voice   = False

    conn_id = request.session.get('connection_id')
    if not conn_id:
        return redirect('connections')
    
    # recreating connection string and engine
    conn = get_object_or_404(ConnectionConfig, pk=conn_id, owner=request.user)
    try:
        engine = connect_db(conn_str_for(conn))
    except Exception as e:
        return redirect('dashboard')
    
    user_prompt = conn.custom_prompt or ""
    audio_form = AudioQueryForm()

    if request.method == 'POST':
        if request.FILES.get('audio_file'):
            is_voice = True
            audio_form = AudioQueryForm(request.POST, request.FILES)
            if audio_form.is_valid():
                aq = audio_form.save(commit=False)
                aq.owner = request.user
                aq.save()
                try:
                    transcript_resp = openai.Audio.transcribe(
                        "whisper-1",
                        open(aq.audio_file.path, "rb")
                    )
                    transcript = transcript_resp["text"].strip()
                    aq.transcript = transcript
                    aq.save()
                except Exception as e:
                    error = f"Transcription failed: {e}"
        else:
            transcript = request.POST.get('question', '').strip()
            if transcript and not error:
                llm        = load_llm()
                embeddings = load_embeddings()
                retriever  = build_retriever(engine, embeddings)
                pipeline   = RAGPipeline(llm, retriever, engine, user_prompt)
                try:
                    sql, rows = pipeline.run(transcript)
                except Exception as e:
                    error = str(e)

    return render(request, 'core/chat.html', {
        'sql':        sql,
        'response':   rows,
        'error':      error,
        'transcript': transcript,
        'is_voice':   is_voice,
        'audio_form': audio_form,
        'user_prompt': user_prompt,
    })


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
    
    editable_cols = [
        col for col in table.columns
        if not col.primary_key and col.name != 'last_update'
    ]

    fields = []
    for col in editable_cols:
        is_date     = isinstance(col.type, Date)
        is_datetime = isinstance(col.type, DateTime)
        fields.append((col.name, '', is_date, is_datetime))

    if request.method == 'POST':
        data = {}
        for col_name, _, is_date, is_datetime in fields:
            raw = request.POST.get(col_name, '').strip()
            if is_date:
                data[col_name] = raw or None
            elif is_datetime:
                # raw comes as 'YYYY-MM-DDTHH:MM', append seconds
                if raw:
                    data[col_name] = raw + ':00'
                else:
                    data[col_name] = None
            else:
                data[col_name] = raw or None

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
    editable_cols = [
        col for col in table.columns
        if not col.primary_key and col.name != 'last_update'
    ]

    with engine.connect() as conn:
        existing = conn.execute(
            select(table).where(table.c[key_col] == pk)
        ).mappings().first()

    fields = []
    for col in editable_cols:
        raw_val = existing.get(col.name)
        is_date     = isinstance(col.type, Date)
        is_datetime = isinstance(col.type, DateTime)

        if is_date and raw_val:
            val = raw_val.isoformat()
        elif is_datetime and raw_val:
            # datetime to 'YYYY-MM-DDTHH:MM'
            val = raw_val.strftime("%Y-%m-%dT%H:%M")
        else:
            val = raw_val or ''

        fields.append((col.name, val, is_date, is_datetime))

    if request.method == 'POST':
        data = {}
        for col_name, _, is_date, is_datetime in fields:
            raw = request.POST.get(col_name, '').strip()
            if is_date:
                data[col_name] = raw or None
            elif is_datetime:
                data[col_name] = raw + ':00' if raw else None
            else:
                data[col_name] = raw or None
        with engine.connect() as conn:
            conn.execute(
                update(table)
                .where(table.c[key_col] == pk)
                .values(**data)
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