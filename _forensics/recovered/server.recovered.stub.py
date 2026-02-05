from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_TITLE = "MOH TIME OS API"
app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8420","http://localhost:5173","http://localhost:3000","*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"ok": True, "service": APP_TITLE}

@app.get("/")
async def root():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:56
    
      56           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
      59           LOAD_GLOBAL              1 (FileResponse + NULL)
                   LOAD_GLOBAL              2 (UI_DIR)
                   LOAD_CONST               1 ('index.html')
                   BINARY_OP               11 (/)
                   CALL                     1
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/overview")
async def get_overview():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:78
    
      78            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
      82            LOAD_GLOBAL              1 (hasattr + NULL)
                    LOAD_GLOBAL              2 (analyzers)
                    LOAD_CONST               1 ('priority_analyzer')
                    CALL                     2
                    TO_BOOL
                    POP_JUMP_IF_FALSE       31 (to L2)
                    NOT_TAKEN
                    LOAD_GLOBAL              2 (analyzers)
                    LOAD_ATTR                4 (priority_analyzer)
                    LOAD_ATTR                7 (analyze + NULL|self)
                    CALL                     0
                    JUMP_FORWARD             1 (to L3)
            L2:     BUILD_LIST               0
            L3:     STORE_FAST               0 (priority_queue)
    
      83            LOAD_GLOBAL              9 (sorted + NULL)
                    LOAD_FAST_BORROW         0 (priority_queue)
                    LOAD_CONST               2 (<code object <lambda> at 0x100984d30, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 83>)
                    MAKE_FUNCTION
                    LOAD_CONST               3 (True)
                    LOAD_CONST               4 (('key', 'reverse'))
                    CALL_KW                  3
                    LOAD_CONST               5 (slice(None, 5, None))
                    BINARY_OP               26 ([])
                    STORE_FAST               1 (top_priorities)
    
      86            LOAD_SMALL_INT           0
                    LOAD_CONST               6 (('datetime',))
                    IMPORT_NAME              5 (datetime)
                    IMPORT_FROM              5 (datetime)
                    STORE_FAST               2 (datetime)
                    POP_TOP
    
      87            LOAD_FAST_BORROW         2 (datetime)
                    LOAD_ATTR               12 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               15 (strftime + NULL|self)
                    LOAD_CONST               7 ('%Y-%m-%d')
                    CALL                     1
                    STORE_FAST               3 (today)
    
      88            LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               19 (query + NULL|self)
    
      89            LOAD_CONST               8 ('SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time')
    
      90            LOAD_FAST_BORROW         3 (today)
                    BUILD_LIST               1
    
      88            CALL                     2
                    STORE_FAST               4 (events)
    
      94            LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               19 (query + NULL|self)
    
      95            LOAD_CONST               9 ('SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC LIMIT 5')
    
      94            CALL                     1
                    STORE_FAST               5 (pending_decisions)
    
      99            LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               19 (query + NULL|self)
    
     100            LOAD_CONST              10 ("SELECT * FROM insights WHERE type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now')) ORDER BY created_at DESC LIMIT 5")
    
      99            CALL                     1
                    STORE_FAST               6 (anomalies)
    
     104            LOAD_CONST              11 ('priorities')
    
     105            LOAD_CONST              12 ('items')
                    LOAD_FAST_BORROW         1 (top_priorities)
    
     106            LOAD_CONST              13 ('total')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         0 (priority_queue)
                    CALL                     1
    
     104            BUILD_MAP                2
    
     108            LOAD_CONST              14 ('calendar')
    
     109            LOAD_CONST              15 ('events')
                    LOAD_FAST_BORROW         4 (events)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      7 (e)
                    SWAP                     2
            L4:     BUILD_LIST               0
                    SWAP                     2
            L5:     FOR_ITER                14 (to L6)
                    STORE_FAST               7 (e)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW         7 (e)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L5)
            L6:     END_FOR
                    POP_ITER
            L7:     SWAP                     2
                    STORE_FAST               7 (e)
    
     110            LOAD_CONST              16 ('event_count')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         4 (events)
                    CALL                     1
    
     108            BUILD_MAP                2
    
     112            LOAD_CONST              17 ('decisions')
    
     113            LOAD_CONST              18 ('pending')
                    LOAD_FAST_BORROW         5 (pending_decisions)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      8 (d)
                    SWAP                     2
            L8:     BUILD_LIST               0
                    SWAP                     2
            L9:     FOR_ITER                14 (to L10)
                    STORE_FAST               8 (d)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW         8 (d)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L9)
           L10:     END_FOR
                    POP_ITER
           L11:     SWAP                     2
                    STORE_FAST               8 (d)
    
     114            LOAD_CONST              19 ('pending_count')
                    LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               25 (count + NULL|self)
                    LOAD_CONST              17 ('decisions')
                    LOAD_CONST              20 ('approved IS NULL')
                    CALL                     2
    
     112            BUILD_MAP                2
    
     116            LOAD_CONST              21 ('anomalies')
    
     117            LOAD_CONST              12 ('items')
                    LOAD_FAST_BORROW         6 (anomalies)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      9 (a)
                    SWAP                     2
           L12:     BUILD_LIST               0
                    SWAP                     2
           L13:     FOR_ITER                14 (to L14)
                    STORE_FAST               9 (a)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW         9 (a)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L13)
           L14:     END_FOR
                    POP_ITER
           L15:     SWAP                     2
                    STORE_FAST               9 (a)
    
     118            LOAD_CONST              13 ('total')
                    LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               25 (count + NULL|self)
                    LOAD_CONST              22 ('insights')
                    LOAD_CONST              23 ("type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now'))")
                    CALL                     2
    
     116            BUILD_MAP                2
    
     120            LOAD_CONST              24 ('sync_status')
                    LOAD_GLOBAL             26 (collectors)
                    LOAD_ATTR               29 (get_status + NULL|self)
                    CALL                     0
    
     103            BUILD_MAP                5
                    RETURN_VALUE
    
      --   L16:     SWAP                     2
                    POP_TOP
    
     109            SWAP                     2
                    STORE_FAST               7 (e)
                    RERAISE                  0
    
      --   L17:     SWAP                     2
                    POP_TOP
    
     113            SWAP                     2
                    STORE_FAST               8 (d)
                    RERAISE                  0
    
      --   L18:     SWAP                     2
                    POP_TOP
    
     117            SWAP                     2
                    STORE_FAST               9 (a)
                    RERAISE                  0
    
      --   L19:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L19 [0] lasti
      L4 to L7 -> L16 [6]
      L7 to L8 -> L19 [0] lasti
      L8 to L11 -> L17 [8]
      L11 to L12 -> L19 [0] lasti
      L12 to L15 -> L18 [10]
      L15 to L19 -> L19 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/time/blocks")
async def get_time_blocks(date, lane):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:129
    
     129           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     132           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               2 (dt)
                   POP_TOP
    
     133           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('BlockManager',))
                   IMPORT_NAME              2 (lib.time_truth)
                   IMPORT_FROM              3 (BlockManager)
                   STORE_FAST               3 (BlockManager)
                   POP_TOP
    
     135           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     136           LOAD_FAST_BORROW         2 (dt)
                   LOAD_ATTR                9 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (date)
    
     138   L2:     LOAD_FAST_BORROW         3 (BlockManager)
                   PUSH_NULL
                   LOAD_GLOBAL             12 (store)
                   CALL                     1
                   STORE_FAST               4 (bm)
    
     139           LOAD_FAST_BORROW         4 (bm)
                   LOAD_ATTR               15 (get_all_blocks + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (date, lane)
                   CALL                     2
                   STORE_FAST               5 (blocks)
    
     142           BUILD_LIST               0
                   STORE_FAST               6 (result)
    
     143           LOAD_FAST_BORROW         5 (blocks)
                   GET_ITER
           L3:     FOR_ITER               242 (to L7)
                   STORE_FAST               7 (block)
    
     145           LOAD_CONST               3 ('id')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               16 (id)
    
     146           LOAD_CONST               4 ('date')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR                2 (date)
    
     147           LOAD_CONST               5 ('start_time')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               18 (start_time)
    
     148           LOAD_CONST               6 ('end_time')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               20 (end_time)
    
     149           LOAD_CONST               7 ('lane')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               22 (lane)
    
     150           LOAD_CONST               8 ('task_id')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               24 (task_id)
    
     151           LOAD_CONST               9 ('is_protected')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               26 (is_protected)
    
     152           LOAD_CONST              10 ('is_buffer')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               28 (is_buffer)
    
     153           LOAD_CONST              11 ('duration_min')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               30 (duration_min)
    
     154           LOAD_CONST              12 ('is_available')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               32 (is_available)
    
     144           BUILD_MAP               10
                   STORE_FAST               8 (block_dict)
    
     157           LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               24 (task_id)
                   TO_BOOL
                   POP_JUMP_IF_FALSE       83 (to L6)
                   NOT_TAKEN
    
     158           LOAD_GLOBAL             12 (store)
                   LOAD_ATTR               35 (get + NULL|self)
                   LOAD_CONST              13 ('tasks')
                   LOAD_FAST_BORROW         7 (block)
                   LOAD_ATTR               24 (task_id)
                   CALL                     2
                   STORE_FAST               9 (task)
    
     159           LOAD_FAST_BORROW         9 (task)
                   TO_BOOL
                   POP_JUMP_IF_FALSE       43 (to L6)
           L4:     NOT_TAKEN
    
     160   L5:     LOAD_FAST_BORROW         9 (task)
                   LOAD_ATTR               35 (get + NULL|self)
                   LOAD_CONST              14 ('title')
                   LOAD_CONST              15 ('')
                   CALL                     2
                   LOAD_FAST_BORROW         8 (block_dict)
                   LOAD_CONST              16 ('task_title')
                   STORE_SUBSCR
    
     161           LOAD_FAST_BORROW         9 (task)
                   LOAD_ATTR               35 (get + NULL|self)
                   LOAD_CONST              17 ('status')
                   LOAD_CONST              15 ('')
                   CALL                     2
                   LOAD_FAST_BORROW         8 (block_dict)
                   LOAD_CONST              18 ('task_status')
                   STORE_SUBSCR
    
     163   L6:     LOAD_FAST_BORROW         6 (result)
                   LOAD_ATTR               37 (append + NULL|self)
                   LOAD_FAST_BORROW         8 (block_dict)
                   CALL                     1
                   POP_TOP
                   JUMP_BACKWARD          244 (to L3)
    
     143   L7:     END_FOR
                   POP_ITER
    
     165           LOAD_CONST               4 ('date')
                   LOAD_FAST_BORROW         0 (date)
                   LOAD_CONST              19 ('blocks')
                   LOAD_FAST_BORROW         6 (result)
                   LOAD_CONST              20 ('total')
                   LOAD_GLOBAL             39 (len + NULL)
                   LOAD_FAST_BORROW         6 (result)
                   CALL                     1
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L8:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L8 [0] lasti
      L5 to L8 -> L8 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/time/summary")
async def get_time_summary(date):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:168
    
     168           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     171           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               1 (dt)
                   POP_TOP
    
     172           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('CalendarSync', 'Scheduler'))
                   IMPORT_NAME              2 (lib.time_truth)
                   IMPORT_FROM              3 (CalendarSync)
                   STORE_FAST               2 (CalendarSync)
                   IMPORT_FROM              4 (Scheduler)
                   STORE_FAST               3 (Scheduler)
                   POP_TOP
    
     174           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     175           LOAD_FAST_BORROW         1 (dt)
                   LOAD_ATTR               11 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               13 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (date)
    
     177   L2:     LOAD_FAST_BORROW         2 (CalendarSync)
                   PUSH_NULL
                   LOAD_GLOBAL             14 (store)
                   CALL                     1
                   STORE_FAST               4 (cs)
    
     178           LOAD_FAST_BORROW         3 (Scheduler)
                   PUSH_NULL
                   LOAD_GLOBAL             14 (store)
                   CALL                     1
                   STORE_FAST               5 (scheduler)
    
     180           LOAD_FAST_BORROW         4 (cs)
                   LOAD_ATTR               17 (get_day_summary + NULL|self)
                   LOAD_FAST_BORROW         0 (date)
                   CALL                     1
                   STORE_FAST               6 (day_summary)
    
     181           LOAD_FAST_BORROW         5 (scheduler)
                   LOAD_ATTR               19 (get_scheduling_summary + NULL|self)
                   LOAD_FAST_BORROW         0 (date)
                   CALL                     1
                   STORE_FAST               7 (scheduling_summary)
    
     184           LOAD_CONST               3 ('date')
                   LOAD_FAST_BORROW         0 (date)
    
     185           LOAD_CONST               4 ('time')
                   LOAD_FAST_BORROW         6 (day_summary)
    
     186           LOAD_CONST               5 ('scheduling')
                   LOAD_FAST_BORROW         7 (scheduling_summary)
    
     183           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/time/brief")
async def get_time_brief(date, format):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:190
    
     190           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     193           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               2 (dt)
                   POP_TOP
    
     194           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('generate_time_brief',))
                   IMPORT_NAME              2 (lib.time_truth)
                   IMPORT_FROM              3 (generate_time_brief)
                   STORE_FAST               3 (generate_time_brief)
                   POP_TOP
    
     196           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     197           LOAD_FAST_BORROW         2 (dt)
                   LOAD_ATTR                9 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (date)
    
     199   L2:     LOAD_FAST_BORROW         3 (generate_time_brief)
                   PUSH_NULL
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (date, format)
                   CALL                     2
                   STORE_FAST               4 (brief)
    
     200           LOAD_CONST               3 ('date')
                   LOAD_FAST_BORROW         0 (date)
                   LOAD_CONST               4 ('brief')
                   LOAD_FAST_BORROW         4 (brief)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/time/schedule")
async def schedule_task(task_id, block_id, date):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:203
    
     203           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     206           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               3 (dt)
                   POP_TOP
    
     207           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('Scheduler',))
                   IMPORT_NAME              2 (lib.time_truth)
                   IMPORT_FROM              3 (Scheduler)
                   STORE_FAST               4 (Scheduler)
                   POP_TOP
    
     209           LOAD_FAST_BORROW         2 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     210           LOAD_FAST_BORROW         3 (dt)
                   LOAD_ATTR                9 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               2 (date)
    
     212   L2:     LOAD_FAST_BORROW         4 (Scheduler)
                   PUSH_NULL
                   LOAD_GLOBAL             12 (store)
                   CALL                     1
                   STORE_FAST               5 (scheduler)
    
     213           LOAD_FAST_BORROW         5 (scheduler)
                   LOAD_ATTR               15 (schedule_specific_task + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (task_id, block_id)
                   LOAD_FAST_BORROW         2 (date)
                   CALL                     3
                   STORE_FAST               6 (result)
    
     216           LOAD_CONST               3 ('success')
                   LOAD_FAST_BORROW         6 (result)
                   LOAD_ATTR               16 (success)
    
     217           LOAD_CONST               4 ('message')
                   LOAD_FAST_BORROW         6 (result)
                   LOAD_ATTR               18 (message)
    
     218           LOAD_CONST               5 ('block_id')
                   LOAD_FAST_BORROW         6 (result)
                   LOAD_ATTR               20 (block_id)
    
     215           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/time/unschedule")
async def unschedule_task(task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:222
    
     222           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     225           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('BlockManager',))
                   IMPORT_NAME              0 (lib.time_truth)
                   IMPORT_FROM              1 (BlockManager)
                   STORE_FAST               1 (BlockManager)
                   POP_TOP
    
     227           LOAD_FAST_BORROW         1 (BlockManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (bm)
    
     228           LOAD_FAST_BORROW         2 (bm)
                   LOAD_ATTR                7 (unschedule_task + NULL|self)
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     1
                   UNPACK_SEQUENCE          2
                   STORE_FAST_STORE_FAST   52 (success, message)
    
     230           LOAD_CONST               2 ('success')
                   LOAD_FAST_BORROW         3 (success)
                   LOAD_CONST               3 ('message')
                   LOAD_FAST_BORROW         4 (message)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/commitments")
async def get_commitments(status, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:237
    
     237           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     240           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CommitmentManager',))
                   IMPORT_NAME              0 (lib.commitment_truth)
                   IMPORT_FROM              1 (CommitmentManager)
                   STORE_FAST               2 (CommitmentManager)
                   POP_TOP
    
     242           LOAD_FAST_BORROW         2 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (cm)
    
     243           LOAD_FAST_BORROW         3 (cm)
                   LOAD_ATTR                7 (get_all_commitments + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (status, limit)
                   LOAD_CONST               2 (('status', 'limit'))
                   CALL_KW                  2
                   STORE_FAST               4 (commitments)
    
     246           LOAD_CONST               3 ('commitments')
    
     260           LOAD_FAST_BORROW         4 (commitments)
                   GET_ITER
    
     246           LOAD_FAST_AND_CLEAR      5 (c)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
    
     260   L3:     FOR_ITER               137 (to L4)
                   STORE_FAST               5 (c)
    
     248           LOAD_CONST               4 ('id')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR                8 (id)
    
     249           LOAD_CONST               5 ('source_type')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               10 (source_type)
    
     250           LOAD_CONST               6 ('source_id')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               12 (source_id)
    
     251           LOAD_CONST               7 ('text')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               14 (text)
    
     252           LOAD_CONST               8 ('owner')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               16 (owner)
    
     253           LOAD_CONST               9 ('target')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               18 (target)
    
     254           LOAD_CONST              10 ('target_date')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               20 (target_date)
    
     255           LOAD_CONST              11 ('status')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               22 (status)
    
     256           LOAD_CONST              12 ('task_id')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               24 (task_id)
    
     257           LOAD_CONST              13 ('confidence')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               26 (confidence)
    
     258           LOAD_CONST              14 ('created_at')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               28 (created_at)
    
     247           BUILD_MAP               11
                   LIST_APPEND              2
                   JUMP_BACKWARD          139 (to L3)
    
     260   L4:     END_FOR
                   POP_ITER
    
     246   L5:     SWAP                     2
                   STORE_FAST               5 (c)
    
     262           LOAD_CONST              15 ('total')
                   LOAD_GLOBAL             31 (len + NULL)
                   LOAD_FAST_BORROW         4 (commitments)
                   CALL                     1
    
     245           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
     246           SWAP                     2
                   STORE_FAST               5 (c)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/commitments/untracked")
async def get_untracked_commitments(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:266
    
     266           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     269           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CommitmentManager',))
                   IMPORT_NAME              0 (lib.commitment_truth)
                   IMPORT_FROM              1 (CommitmentManager)
                   STORE_FAST               1 (CommitmentManager)
                   POP_TOP
    
     271           LOAD_FAST_BORROW         1 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (cm)
    
     272           LOAD_FAST_BORROW         2 (cm)
                   LOAD_ATTR                7 (get_untracked_commitments + NULL|self)
                   LOAD_FAST_BORROW         0 (limit)
                   LOAD_CONST               2 (('limit',))
                   CALL_KW                  1
                   STORE_FAST               3 (commitments)
    
     275           LOAD_CONST               3 ('commitments')
    
     284           LOAD_FAST_BORROW         3 (commitments)
                   GET_ITER
    
     275           LOAD_FAST_AND_CLEAR      4 (c)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
    
     284   L3:     FOR_ITER                77 (to L4)
                   STORE_FAST               4 (c)
    
     277           LOAD_CONST               4 ('id')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR                8 (id)
    
     278           LOAD_CONST               5 ('text')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR               10 (text)
    
     279           LOAD_CONST               6 ('owner')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR               12 (owner)
    
     280           LOAD_CONST               7 ('target_date')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR               14 (target_date)
    
     281           LOAD_CONST               8 ('confidence')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR               16 (confidence)
    
     282           LOAD_CONST               9 ('source_type')
                   LOAD_FAST_BORROW         4 (c)
                   LOAD_ATTR               18 (source_type)
    
     276           BUILD_MAP                6
                   LIST_APPEND              2
                   JUMP_BACKWARD           79 (to L3)
    
     284   L4:     END_FOR
                   POP_ITER
    
     275   L5:     SWAP                     2
                   STORE_FAST               4 (c)
    
     286           LOAD_CONST              10 ('total')
                   LOAD_GLOBAL             21 (len + NULL)
                   LOAD_FAST_BORROW         3 (commitments)
                   CALL                     1
    
     274           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
     275           SWAP                     2
                   STORE_FAST               4 (c)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/commitments/due")
async def get_commitments_due(date):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:290
    
     290           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     293           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               1 (dt)
                   POP_TOP
    
     294           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('CommitmentManager',))
                   IMPORT_NAME              2 (lib.commitment_truth)
                   IMPORT_FROM              3 (CommitmentManager)
                   STORE_FAST               2 (CommitmentManager)
                   POP_TOP
    
     296           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     297           LOAD_FAST_BORROW         1 (dt)
                   LOAD_ATTR                9 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (date)
    
     299   L2:     LOAD_FAST_BORROW         2 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL             12 (store)
                   CALL                     1
                   STORE_FAST               3 (cm)
    
     300           LOAD_FAST_BORROW         3 (cm)
                   LOAD_ATTR               15 (get_commitments_due + NULL|self)
                   LOAD_FAST_BORROW         0 (date)
                   CALL                     1
                   STORE_FAST               4 (commitments)
    
     303           LOAD_CONST               3 ('date')
                   LOAD_FAST                0 (date)
    
     304           LOAD_CONST               4 ('commitments')
    
     313           LOAD_FAST_BORROW         4 (commitments)
                   GET_ITER
    
     304           LOAD_FAST_AND_CLEAR      5 (c)
                   SWAP                     2
           L3:     BUILD_LIST               0
                   SWAP                     2
    
     313   L4:     FOR_ITER                77 (to L5)
                   STORE_FAST               5 (c)
    
     306           LOAD_CONST               5 ('id')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               16 (id)
    
     307           LOAD_CONST               6 ('text')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               18 (text)
    
     308           LOAD_CONST               7 ('owner')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               20 (owner)
    
     309           LOAD_CONST               8 ('target_date')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               22 (target_date)
    
     310           LOAD_CONST               9 ('status')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               24 (status)
    
     311           LOAD_CONST              10 ('task_id')
                   LOAD_FAST_BORROW         5 (c)
                   LOAD_ATTR               26 (task_id)
    
     305           BUILD_MAP                6
                   LIST_APPEND              2
                   JUMP_BACKWARD           79 (to L4)
    
     313   L5:     END_FOR
                   POP_ITER
    
     304   L6:     SWAP                     2
                   STORE_FAST               5 (c)
    
     315           LOAD_CONST              11 ('total')
                   LOAD_GLOBAL             29 (len + NULL)
                   LOAD_FAST_BORROW         4 (commitments)
                   CALL                     1
    
     302           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L7:     SWAP                     2
                   POP_TOP
    
     304           SWAP                     2
                   STORE_FAST               5 (c)
                   RERAISE                  0
    
      --   L8:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L8 [0] lasti
      L3 to L6 -> L7 [5]
      L6 to L8 -> L8 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/commitments/summary")
async def get_commitments_summary():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:319
    
     319           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     322           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CommitmentManager',))
                   IMPORT_NAME              0 (lib.commitment_truth)
                   IMPORT_FROM              1 (CommitmentManager)
                   STORE_FAST               0 (CommitmentManager)
                   POP_TOP
    
     324           LOAD_FAST_BORROW         0 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               1 (cm)
    
     325           LOAD_FAST_BORROW         1 (cm)
                   LOAD_ATTR                7 (get_summary + NULL|self)
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/commitments/{commitment_id}/link")
async def link_commitment(commitment_id, task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:328
    
     328           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     331           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CommitmentManager',))
                   IMPORT_NAME              0 (lib.commitment_truth)
                   IMPORT_FROM              1 (CommitmentManager)
                   STORE_FAST               2 (CommitmentManager)
                   POP_TOP
    
     333           LOAD_FAST_BORROW         2 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (cm)
    
     334           LOAD_FAST_BORROW         3 (cm)
                   LOAD_ATTR                7 (link_commitment_to_task + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (commitment_id, task_id)
                   CALL                     2
                   UNPACK_SEQUENCE          2
                   STORE_FAST_STORE_FAST   69 (success, message)
    
     336           LOAD_CONST               2 ('success')
                   LOAD_FAST_BORROW         4 (success)
                   LOAD_CONST               3 ('message')
                   LOAD_FAST_BORROW         5 (message)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/commitments/{commitment_id}/done")
async def mark_commitment_done(commitment_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:339
    
     339           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     342           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CommitmentManager',))
                   IMPORT_NAME              0 (lib.commitment_truth)
                   IMPORT_FROM              1 (CommitmentManager)
                   STORE_FAST               1 (CommitmentManager)
                   POP_TOP
    
     344           LOAD_FAST_BORROW         1 (CommitmentManager)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (cm)
    
     345           LOAD_FAST_BORROW         2 (cm)
                   LOAD_ATTR                7 (mark_done + NULL|self)
                   LOAD_FAST_BORROW         0 (commitment_id)
                   CALL                     1
                   UNPACK_SEQUENCE          2
                   STORE_FAST_STORE_FAST   52 (success, message)
    
     347           LOAD_CONST               2 ('success')
                   LOAD_FAST_BORROW         3 (success)
                   LOAD_CONST               3 ('message')
                   LOAD_FAST_BORROW         4 (message)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/capacity/lanes")
async def get_capacity_lanes():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:354
    
     354           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     357           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CapacityCalculator',))
                   IMPORT_NAME              0 (lib.capacity_truth)
                   IMPORT_FROM              1 (CapacityCalculator)
                   STORE_FAST               0 (CapacityCalculator)
                   POP_TOP
    
     359           LOAD_FAST_BORROW         0 (CapacityCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               1 (calc)
    
     360           LOAD_FAST_BORROW         1 (calc)
                   LOAD_ATTR                7 (get_lanes + NULL|self)
                   CALL                     0
                   STORE_FAST               2 (lanes)
    
     362           LOAD_CONST               2 ('lanes')
                   LOAD_FAST_BORROW         2 (lanes)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              9 (len + NULL)
                   LOAD_FAST_BORROW         2 (lanes)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/capacity/utilization")
async def get_capacity_utilization(date, lane):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:365
    
     365           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     368           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date',))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               2 (dt)
                   POP_TOP
    
     369           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('CapacityCalculator',))
                   IMPORT_NAME              2 (lib.capacity_truth)
                   IMPORT_FROM              3 (CapacityCalculator)
                   STORE_FAST               3 (CapacityCalculator)
                   POP_TOP
    
     371           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        31 (to L2)
                   NOT_TAKEN
    
     372           LOAD_FAST_BORROW         2 (dt)
                   LOAD_ATTR                9 (today + NULL|self)
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (date)
    
     374   L2:     LOAD_FAST_BORROW         3 (CapacityCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL             12 (store)
                   CALL                     1
                   STORE_FAST               4 (calc)
    
     376           LOAD_FAST_BORROW         1 (lane)
                   TO_BOOL
                   POP_JUMP_IF_FALSE       84 (to L5)
           L3:     NOT_TAKEN
    
     377   L4:     LOAD_FAST_BORROW         4 (calc)
                   LOAD_ATTR               15 (get_lane_utilization + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 16 (lane, date)
                   CALL                     2
                   STORE_FAST               5 (util)
    
     379           LOAD_CONST               3 ('date')
                   LOAD_FAST_BORROW         0 (date)
    
     380           LOAD_CONST               4 ('lane')
                   LOAD_FAST_BORROW         1 (lane)
    
     381           LOAD_CONST               5 ('capacity_min')
                   LOAD_FAST_BORROW         5 (util)
                   LOAD_ATTR               16 (capacity_min)
    
     382           LOAD_CONST               6 ('scheduled_min')
                   LOAD_FAST_BORROW         5 (util)
                   LOAD_ATTR               18 (scheduled_min)
    
     383           LOAD_CONST               7 ('available_min')
                   LOAD_FAST_BORROW         5 (util)
                   LOAD_ATTR               20 (available_min)
    
     384           LOAD_CONST               8 ('utilization_pct')
                   LOAD_FAST_BORROW         5 (util)
                   LOAD_ATTR               22 (utilization_pct)
    
     385           LOAD_CONST               9 ('is_overloaded')
                   LOAD_FAST_BORROW         5 (util)
                   LOAD_ATTR               24 (is_overloaded)
    
     378           BUILD_MAP                7
                   RETURN_VALUE
    
     388   L5:     LOAD_FAST_BORROW         4 (calc)
                   LOAD_ATTR               27 (get_capacity_summary + NULL|self)
                   LOAD_FAST_BORROW         0 (date)
                   CALL                     1
                   RETURN_VALUE
    
      --   L6:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L6 [0] lasti
      L4 to L6 -> L6 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/capacity/forecast")
async def get_capacity_forecast(lane, days):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:391
    
     391           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     394           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('CapacityCalculator',))
                   IMPORT_NAME              0 (lib.capacity_truth)
                   IMPORT_FROM              1 (CapacityCalculator)
                   STORE_FAST               2 (CapacityCalculator)
                   POP_TOP
    
     396           LOAD_FAST_BORROW         2 (CapacityCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (calc)
    
     397           LOAD_FAST_BORROW         3 (calc)
                   LOAD_ATTR                7 (forecast_capacity + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (lane, days)
                   CALL                     2
                   STORE_FAST               4 (forecast)
    
     400           LOAD_CONST               2 ('lane')
                   LOAD_FAST                0 (lane)
    
     401           LOAD_CONST               3 ('days')
                   LOAD_FAST                1 (days)
    
     402           LOAD_CONST               4 ('forecast')
    
     409           LOAD_FAST_BORROW         4 (forecast)
                   GET_ITER
    
     402           LOAD_FAST_AND_CLEAR      5 (f)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
    
     409   L3:     FOR_ITER                53 (to L4)
                   STORE_FAST               5 (f)
    
     404           LOAD_CONST               5 ('date')
                   LOAD_FAST_BORROW         5 (f)
                   LOAD_ATTR                8 (date)
    
     405           LOAD_CONST               6 ('utilization_pct')
                   LOAD_FAST_BORROW         5 (f)
                   LOAD_ATTR               10 (utilization_pct)
    
     406           LOAD_CONST               7 ('available_min')
                   LOAD_FAST_BORROW         5 (f)
                   LOAD_ATTR               12 (available_min)
    
     407           LOAD_CONST               8 ('is_overloaded')
                   LOAD_FAST_BORROW         5 (f)
                   LOAD_ATTR               14 (is_overloaded)
    
     403           BUILD_MAP                4
                   LIST_APPEND              2
                   JUMP_BACKWARD           55 (to L3)
    
     409   L4:     END_FOR
                   POP_ITER
    
     402   L5:     SWAP                     2
                   STORE_FAST               5 (f)
    
     399           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
     402           SWAP                     2
                   STORE_FAST               5 (f)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [7]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/capacity/debt")
async def get_capacity_debt(lane):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:414
    
     414           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     417           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DebtTracker',))
                   IMPORT_NAME              0 (lib.capacity_truth)
                   IMPORT_FROM              1 (DebtTracker)
                   STORE_FAST               1 (DebtTracker)
                   POP_TOP
    
     419           LOAD_FAST_BORROW         1 (DebtTracker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (tracker)
    
     420           LOAD_FAST_BORROW         2 (tracker)
                   LOAD_ATTR                7 (get_debt_report + NULL|self)
                   LOAD_FAST_BORROW         0 (lane)
                   CALL                     1
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/capacity/debt/accrue")
async def accrue_debt(lane, amount, reason, task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:423
    
     423           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     426           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DebtTracker',))
                   IMPORT_NAME              0 (lib.capacity_truth)
                   IMPORT_FROM              1 (DebtTracker)
                   STORE_FAST               4 (DebtTracker)
                   POP_TOP
    
     428           LOAD_FAST_BORROW         4 (DebtTracker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               5 (tracker)
    
     429           LOAD_FAST_BORROW         5 (tracker)
                   LOAD_ATTR                7 (accrue_debt + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (lane, amount)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 35 (reason, task_id)
                   CALL                     4
                   STORE_FAST               6 (debt_id)
    
     431           LOAD_CONST               2 ('success')
                   LOAD_CONST               3 (True)
                   LOAD_CONST               4 ('debt_id')
                   LOAD_FAST_BORROW         6 (debt_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/capacity/debt/{debt_id}/resolve")
async def resolve_debt(debt_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:434
    
     434           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     437           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DebtTracker',))
                   IMPORT_NAME              0 (lib.capacity_truth)
                   IMPORT_FROM              1 (DebtTracker)
                   STORE_FAST               1 (DebtTracker)
                   POP_TOP
    
     439           LOAD_FAST_BORROW         1 (DebtTracker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (tracker)
    
     440           LOAD_FAST_BORROW         2 (tracker)
                   LOAD_ATTR                7 (resolve_debt + NULL|self)
                   LOAD_FAST_BORROW         0 (debt_id)
                   CALL                     1
                   UNPACK_SEQUENCE          2
                   STORE_FAST_STORE_FAST   52 (success, message)
    
     442           LOAD_CONST               2 ('success')
                   LOAD_FAST_BORROW         3 (success)
                   LOAD_CONST               3 ('message')
                   LOAD_FAST_BORROW         4 (message)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/health")
async def get_clients_health(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:449
    
     449           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     452           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('HealthCalculator',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (HealthCalculator)
                   STORE_FAST               1 (HealthCalculator)
                   POP_TOP
    
     454           LOAD_FAST_BORROW         1 (HealthCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (calc)
    
     455           LOAD_GLOBAL              4 (store)
                   LOAD_ATTR                7 (query + NULL|self)
                   LOAD_CONST               2 ('SELECT id, name FROM clients LIMIT ?')
                   LOAD_FAST_BORROW         0 (limit)
                   BUILD_LIST               1
                   CALL                     2
                   STORE_FAST               3 (clients)
    
     457           BUILD_LIST               0
                   STORE_FAST               4 (results)
    
     458           LOAD_FAST_BORROW         3 (clients)
                   GET_ITER
           L2:     FOR_ITER               128 (to L3)
                   STORE_FAST               5 (client)
    
     459           LOAD_FAST_BORROW         2 (calc)
                   LOAD_ATTR                9 (compute_health_score + NULL|self)
                   LOAD_FAST_BORROW         5 (client)
                   LOAD_CONST               3 ('id')
                   BINARY_OP               26 ([])
                   CALL                     1
                   STORE_FAST               6 (health)
    
     460           LOAD_FAST_BORROW         4 (results)
                   LOAD_ATTR               11 (append + NULL|self)
    
     461           LOAD_CONST               4 ('client_id')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               12 (client_id)
    
     462           LOAD_CONST               5 ('name')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               14 (client_name)
    
     463           LOAD_CONST               6 ('health_score')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               16 (health_score)
    
     464           LOAD_CONST               7 ('tier')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               18 (tier)
    
     465           LOAD_CONST               8 ('trend')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               20 (trend)
    
     466           LOAD_CONST               9 ('at_risk')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               22 (at_risk)
    
     467           LOAD_CONST              10 ('factors')
                   LOAD_FAST_BORROW         6 (health)
                   LOAD_ATTR               24 (factors)
    
     460           BUILD_MAP                7
                   CALL                     1
                   POP_TOP
                   JUMP_BACKWARD          130 (to L2)
    
     458   L3:     END_FOR
                   POP_ITER
    
     471           LOAD_FAST_BORROW         4 (results)
                   LOAD_ATTR               27 (sort + NULL|self)
                   LOAD_CONST              11 (<code object <lambda> at 0x100919a70, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 471>)
                   MAKE_FUNCTION
                   LOAD_CONST              12 (('key',))
                   CALL_KW                  1
                   POP_TOP
    
     473           LOAD_CONST              13 ('clients')
                   LOAD_FAST_BORROW         4 (results)
                   LOAD_CONST              14 ('total')
                   LOAD_GLOBAL             29 (len + NULL)
                   LOAD_FAST_BORROW         4 (results)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/at-risk")
async def get_at_risk_clients(threshold):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:476
    
     476           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     479           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('HealthCalculator',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (HealthCalculator)
                   STORE_FAST               1 (HealthCalculator)
                   POP_TOP
    
     481           LOAD_FAST_BORROW         1 (HealthCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (calc)
    
     482           LOAD_FAST_BORROW         2 (calc)
                   LOAD_ATTR                7 (get_at_risk_clients + NULL|self)
                   LOAD_FAST_BORROW         0 (threshold)
                   CALL                     1
                   STORE_FAST               3 (at_risk)
    
     485           LOAD_CONST               2 ('threshold')
                   LOAD_FAST                0 (threshold)
    
     486           LOAD_CONST               3 ('clients')
    
     494           LOAD_FAST_BORROW         3 (at_risk)
                   GET_ITER
    
     486           LOAD_FAST_AND_CLEAR      4 (h)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
    
     494   L3:     FOR_ITER                65 (to L4)
                   STORE_FAST               4 (h)
    
     488           LOAD_CONST               4 ('client_id')
                   LOAD_FAST_BORROW         4 (h)
                   LOAD_ATTR                8 (client_id)
    
     489           LOAD_CONST               5 ('name')
                   LOAD_FAST_BORROW         4 (h)
                   LOAD_ATTR               10 (client_name)
    
     490           LOAD_CONST               6 ('health_score')
                   LOAD_FAST_BORROW         4 (h)
                   LOAD_ATTR               12 (health_score)
    
     491           LOAD_CONST               7 ('trend')
                   LOAD_FAST_BORROW         4 (h)
                   LOAD_ATTR               14 (trend)
    
     492           LOAD_CONST               8 ('factors')
                   LOAD_FAST_BORROW         4 (h)
                   LOAD_ATTR               16 (factors)
    
     487           BUILD_MAP                5
                   LIST_APPEND              2
                   JUMP_BACKWARD           67 (to L3)
    
     494   L4:     END_FOR
                   POP_ITER
    
     486   L5:     SWAP                     2
                   STORE_FAST               4 (h)
    
     496           LOAD_CONST               9 ('total')
                   LOAD_GLOBAL             19 (len + NULL)
                   LOAD_FAST_BORROW         3 (at_risk)
                   CALL                     1
    
     484           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
     486           SWAP                     2
                   STORE_FAST               4 (h)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [5]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/{client_id}/health")
async def get_client_health(client_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:500
    
     500           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     503           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('HealthCalculator',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (HealthCalculator)
                   STORE_FAST               1 (HealthCalculator)
                   POP_TOP
    
     505           LOAD_FAST_BORROW         1 (HealthCalculator)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (calc)
    
     506           LOAD_FAST_BORROW         2 (calc)
                   LOAD_ATTR                7 (get_client_summary + NULL|self)
                   LOAD_FAST_BORROW         0 (client_id)
                   CALL                     1
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/{client_id}/projects")
async def get_client_projects(client_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:509
    
     509           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     512           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('ClientLinker',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (ClientLinker)
                   STORE_FAST               1 (ClientLinker)
                   POP_TOP
    
     514           LOAD_FAST_BORROW         1 (ClientLinker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               2 (linker)
    
     515           LOAD_FAST_BORROW         2 (linker)
                   LOAD_ATTR                7 (get_client_projects + NULL|self)
                   LOAD_FAST_BORROW         0 (client_id)
                   CALL                     1
                   STORE_FAST               3 (projects)
    
     517           LOAD_CONST               2 ('client_id')
                   LOAD_FAST_BORROW         0 (client_id)
                   LOAD_CONST               3 ('projects')
                   LOAD_FAST_BORROW         3 (projects)
                   LOAD_CONST               4 ('total')
                   LOAD_GLOBAL              9 (len + NULL)
                   LOAD_FAST_BORROW         3 (projects)
                   CALL                     1
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/clients/link")
async def link_project_to_client(project_id, client_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:520
    
     520           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     523           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('ClientLinker',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (ClientLinker)
                   STORE_FAST               2 (ClientLinker)
                   POP_TOP
    
     525           LOAD_FAST_BORROW         2 (ClientLinker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (linker)
    
     526           LOAD_FAST_BORROW         3 (linker)
                   LOAD_ATTR                7 (link_project_to_client + NULL|self)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (project_id, client_id)
                   CALL                     2
                   UNPACK_SEQUENCE          2
                   STORE_FAST_STORE_FAST   69 (success, message)
    
     528           LOAD_CONST               2 ('success')
                   LOAD_FAST_BORROW         4 (success)
                   LOAD_CONST               3 ('message')
                   LOAD_FAST_BORROW         5 (message)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/linking-stats")
async def get_linking_stats():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:531
    
     531           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     534           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('ClientLinker',))
                   IMPORT_NAME              0 (lib.client_truth)
                   IMPORT_FROM              1 (ClientLinker)
                   STORE_FAST               0 (ClientLinker)
                   POP_TOP
    
     536           LOAD_FAST_BORROW         0 (ClientLinker)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               1 (linker)
    
     537           LOAD_FAST_BORROW         1 (linker)
                   LOAD_ATTR                7 (get_linking_stats + NULL|self)
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/tasks")
async def get_tasks(status, project, assignee, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:543
    
     543            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
     551            BUILD_LIST               0
                    STORE_FAST               4 (conditions)
    
     552            BUILD_LIST               0
                    STORE_FAST               5 (params)
    
     554            LOAD_FAST_BORROW         0 (status)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       35 (to L2)
                    NOT_TAKEN
    
     555            LOAD_FAST_BORROW         4 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               1 ('status = ?')
                    CALL                     1
                    POP_TOP
    
     556            LOAD_FAST_BORROW         5 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         0 (status)
                    CALL                     1
                    POP_TOP
    
     557    L2:     LOAD_FAST_BORROW         1 (project)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L5)
            L3:     NOT_TAKEN
    
     558    L4:     LOAD_FAST_BORROW         4 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               2 ('project LIKE ?')
                    CALL                     1
                    POP_TOP
    
     559            LOAD_FAST_BORROW         5 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               3 ('%')
                    LOAD_FAST_BORROW         1 (project)
                    FORMAT_SIMPLE
                    LOAD_CONST               3 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
     560    L5:     LOAD_FAST_BORROW         2 (assignee)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L8)
            L6:     NOT_TAKEN
    
     561    L7:     LOAD_FAST_BORROW         4 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               4 ('assignee LIKE ?')
                    CALL                     1
                    POP_TOP
    
     562            LOAD_FAST_BORROW         5 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               3 ('%')
                    LOAD_FAST_BORROW         2 (assignee)
                    FORMAT_SIMPLE
                    LOAD_CONST               3 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
     564    L8:     LOAD_FAST_BORROW         4 (conditions)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       18 (to L11)
            L9:     NOT_TAKEN
           L10:     LOAD_CONST               5 (' AND ')
                    LOAD_ATTR                3 (join + NULL|self)
                    LOAD_FAST_BORROW         4 (conditions)
                    CALL                     1
                    JUMP_FORWARD             1 (to L12)
           L11:     LOAD_CONST               6 ('1=1')
           L12:     STORE_FAST               6 (where)
    
     566            LOAD_GLOBAL              4 (store)
                    LOAD_ATTR                7 (query + NULL|self)
    
     567            LOAD_CONST               7 ('SELECT t.*, c.name as client_name, p.name as project_name \n            FROM tasks t \n            LEFT JOIN clients c ON t.client_id = c.id\n            LEFT JOIN projects p ON t.project = p.id\n            WHERE ')
    
     571            LOAD_FAST_BORROW         6 (where)
                    FORMAT_SIMPLE
                    LOAD_CONST               8 (' \n            ORDER BY t.priority DESC, t.due_date ASC LIMIT ?')
    
     567            BUILD_STRING             3
    
     573            LOAD_FAST_BORROW_LOAD_FAST_BORROW 83 (params, limit)
                    BUILD_LIST               1
                    BINARY_OP                0 (+)
    
     566            CALL                     2
                    STORE_FAST               7 (tasks)
    
     577            LOAD_CONST               9 ('items')
                    LOAD_FAST_BORROW         7 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      8 (t)
                    SWAP                     2
           L13:     BUILD_LIST               0
                    SWAP                     2
           L14:     FOR_ITER                14 (to L15)
                    STORE_FAST               8 (t)
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         8 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L14)
           L15:     END_FOR
                    POP_ITER
           L16:     SWAP                     2
                    STORE_FAST               8 (t)
    
     578            LOAD_CONST              10 ('total')
                    LOAD_GLOBAL              4 (store)
                    LOAD_ATTR               11 (count + NULL|self)
                    LOAD_CONST              11 ('tasks')
                    LOAD_FAST_BORROW         4 (conditions)
                    TO_BOOL
                    POP_JUMP_IF_FALSE        8 (to L19)
           L17:     NOT_TAKEN
           L18:     LOAD_FAST_BORROW         6 (where)
                    CALL                     2
    
     576            BUILD_MAP                2
                    RETURN_VALUE
    
     578   L19:     LOAD_CONST              12 (None)
                    CALL                     2
    
     576            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L20:     SWAP                     2
                    POP_TOP
    
     577            SWAP                     2
                    STORE_FAST               8 (t)
                    RERAISE                  0
    
      --   L21:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L21 [0] lasti
      L4 to L6 -> L21 [0] lasti
      L7 to L9 -> L21 [0] lasti
      L10 to L13 -> L21 [0] lasti
      L13 to L16 -> L20 [3]
      L16 to L17 -> L21 [0] lasti
      L18 to L21 -> L21 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/tasks/{task_id}")
async def get_task(task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:613
    
     613           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     616           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               1 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     2
                   STORE_FAST               1 (task)
    
     617           LOAD_FAST_BORROW         1 (task)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
     618           LOAD_GLOBAL              5 (HTTPException + NULL)
                   LOAD_CONST               2 (404)
                   LOAD_CONST               3 ('Task not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
     619   L2:     LOAD_GLOBAL              7 (dict + NULL)
                   LOAD_FAST_BORROW         1 (task)
                   CALL                     1
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks")
async def create_task(body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:622
    
     622           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     625           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('TaskHandler',))
                   IMPORT_NAME              0 (lib.executor.handlers.task)
                   IMPORT_FROM              1 (TaskHandler)
                   STORE_FAST               1 (TaskHandler)
                   POP_TOP
    
     626           LOAD_SMALL_INT           0
                   LOAD_CONST               2 (('create_task_bundle', 'mark_applied'))
                   IMPORT_NAME              2 (lib.change_bundles)
                   IMPORT_FROM              3 (create_task_bundle)
                   STORE_FAST               2 (create_task_bundle)
                   IMPORT_FROM              4 (mark_applied)
                   STORE_FAST               3 (mark_applied)
                   POP_TOP
    
     628           LOAD_FAST_BORROW         1 (TaskHandler)
                   PUSH_NULL
                   LOAD_GLOBAL             10 (store)
                   CALL                     1
                   STORE_FAST               4 (handler)
    
     630           LOAD_FAST_BORROW         0 (body)
                   LOAD_ATTR               13 (dict + NULL|self)
                   LOAD_CONST               3 (True)
                   LOAD_CONST               4 (('exclude_none',))
                   CALL_KW                  1
                   STORE_FAST               5 (task_data)
    
     631           LOAD_CONST               5 ('task_')
                   LOAD_GLOBAL             14 (datetime)
                   LOAD_ATTR               16 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               19 (strftime + NULL|self)
                   LOAD_CONST               6 ('%Y%m%d_%H%M%S_%f')
                   CALL                     1
                   LOAD_CONST               7 (slice(None, 20, None))
                   BINARY_OP               26 ([])
                   FORMAT_SIMPLE
                   BUILD_STRING             2
                   STORE_FAST               6 (task_id)
    
     632           LOAD_FAST_BORROW_LOAD_FAST_BORROW 101 (task_id, task_data)
                   LOAD_CONST               8 ('id')
                   STORE_SUBSCR
    
     633           LOAD_CONST               9 ('time_os')
                   LOAD_FAST_BORROW         5 (task_data)
                   LOAD_CONST              10 ('source')
                   STORE_SUBSCR
    
     636           LOAD_FAST_BORROW         2 (create_task_bundle)
                   PUSH_NULL
    
     637           LOAD_CONST              11 ('Create task: ')
                   LOAD_FAST_BORROW         0 (body)
                   LOAD_ATTR               20 (title)
                   LOAD_CONST              12 (slice(None, 50, None))
                   BINARY_OP               26 ([])
                   FORMAT_SIMPLE
                   BUILD_STRING             2
    
     638           LOAD_CONST               8 ('id')
                   LOAD_FAST_BORROW         6 (task_id)
                   LOAD_CONST              13 ('type')
                   LOAD_CONST              14 ('create')
                   LOAD_CONST              15 ('data')
                   LOAD_FAST_BORROW         5 (task_data)
                   BUILD_MAP                3
                   BUILD_LIST               1
    
     639           BUILD_MAP                0
    
     636           LOAD_CONST              16 (('description', 'updates', 'pre_images'))
                   CALL_KW                  3
                   STORE_FAST               7 (bundle)
    
     642           LOAD_FAST_BORROW         4 (handler)
                   LOAD_ATTR               23 (execute + NULL|self)
    
     643           LOAD_CONST              17 ('action_type')
                   LOAD_CONST              14 ('create')
    
     644           LOAD_CONST              15 ('data')
                   LOAD_FAST_BORROW         5 (task_data)
    
     642           BUILD_MAP                2
                   CALL                     1
                   STORE_FAST               8 (result)
    
     647           LOAD_FAST_BORROW         8 (result)
                   LOAD_ATTR               25 (get + NULL|self)
                   LOAD_CONST              18 ('success')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE       31 (to L2)
                   NOT_TAKEN
    
     648           LOAD_FAST_BORROW         3 (mark_applied)
                   PUSH_NULL
                   LOAD_FAST_BORROW         7 (bundle)
                   LOAD_CONST               8 ('id')
                   BINARY_OP               26 ([])
                   CALL                     1
                   POP_TOP
    
     650           LOAD_CONST              18 ('success')
                   LOAD_CONST               3 (True)
    
     651           LOAD_CONST              19 ('task_id')
                   LOAD_FAST_BORROW         6 (task_id)
    
     652           LOAD_CONST              20 ('bundle_id')
                   LOAD_FAST_BORROW         7 (bundle)
                   LOAD_CONST               8 ('id')
                   BINARY_OP               26 ([])
    
     649           BUILD_MAP                3
                   RETURN_VALUE
    
     655   L2:     LOAD_GLOBAL             27 (HTTPException + NULL)
                   LOAD_CONST              21 (500)
                   LOAD_FAST_BORROW         8 (result)
                   LOAD_ATTR               25 (get + NULL|self)
                   LOAD_CONST              22 ('error')
                   LOAD_CONST              23 ('Task creation failed')
                   CALL                     2
                   CALL                     2
                   RAISE_VARARGS            1
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.put("/api/tasks/{task_id}")
async def update_task(task_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:658
    
     658            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
     661            LOAD_SMALL_INT           0
                    LOAD_CONST               1 (('create_task_bundle', 'mark_applied'))
                    IMPORT_NAME              0 (lib.change_bundles)
                    IMPORT_FROM              1 (create_task_bundle)
                    STORE_FAST               2 (create_task_bundle)
                    IMPORT_FROM              2 (mark_applied)
                    STORE_FAST               3 (mark_applied)
                    POP_TOP
    
     663            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (get + NULL|self)
                    LOAD_CONST               2 ('tasks')
                    LOAD_FAST_BORROW         0 (task_id)
                    CALL                     2
                    STORE_FAST               4 (task)
    
     664            LOAD_FAST_BORROW         4 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
     665            LOAD_GLOBAL             11 (HTTPException + NULL)
                    LOAD_CONST               3 (404)
                    LOAD_CONST               4 ('Task not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
     668    L2:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               13 (dict + NULL|self)
                    CALL                     0
                    LOAD_ATTR               15 (items + NULL|self)
                    CALL                     0
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (k)
                    LOAD_FAST_AND_CLEAR      6 (v)
                    SWAP                     3
            L3:     BUILD_MAP                0
                    SWAP                     2
            L4:     FOR_ITER                13 (to L7)
                    UNPACK_SEQUENCE          2
                    STORE_FAST_STORE_FAST   86 (k, v)
                    LOAD_FAST_BORROW         6 (v)
            L5:     POP_JUMP_IF_NOT_NONE     3 (to L6)
                    NOT_TAKEN
                    JUMP_BACKWARD           11 (to L4)
            L6:     LOAD_FAST_BORROW_LOAD_FAST_BORROW 86 (k, v)
                    MAP_ADD                  2
                    JUMP_BACKWARD           15 (to L4)
            L7:     END_FOR
                    POP_ITER
            L8:     STORE_FAST               7 (update_data)
                    STORE_FAST               5 (k)
                    STORE_FAST               6 (v)
    
     669            LOAD_FAST_BORROW         7 (update_data)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L9)
                    NOT_TAKEN
    
     670            LOAD_GLOBAL             11 (HTTPException + NULL)
                    LOAD_CONST               5 (400)
                    LOAD_CONST               6 ('No fields to update')
                    CALL                     2
                    RAISE_VARARGS            1
    
     672    L9:     LOAD_GLOBAL             16 (datetime)
                    LOAD_ATTR               18 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               21 (isoformat + NULL|self)
                    CALL                     0
                    LOAD_FAST_BORROW         7 (update_data)
                    LOAD_CONST               7 ('updated_at')
                    STORE_SUBSCR
    
     675            LOAD_FAST_BORROW         7 (update_data)
                    LOAD_ATTR               23 (keys + NULL|self)
                    CALL                     0
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (k)
                    SWAP                     2
           L10:     BUILD_MAP                0
                    SWAP                     2
           L11:     FOR_ITER                28 (to L14)
                    STORE_FAST_LOAD_FAST    85 (k, k)
                    LOAD_CONST               7 ('updated_at')
                    COMPARE_OP             119 (bool(!=))
           L12:     POP_JUMP_IF_TRUE         3 (to L13)
                    NOT_TAKEN
                    JUMP_BACKWARD           11 (to L11)
           L13:     LOAD_FAST_BORROW_LOAD_FAST_BORROW 84 (k, task)
                    LOAD_ATTR                9 (get + NULL|self)
                    LOAD_FAST_BORROW         5 (k)
                    CALL                     1
                    MAP_ADD                  2
                    JUMP_BACKWARD           30 (to L11)
           L14:     END_FOR
                    POP_ITER
           L15:     STORE_FAST               8 (pre_image)
                    STORE_FAST               5 (k)
    
     676            LOAD_FAST_BORROW         2 (create_task_bundle)
                    PUSH_NULL
    
     677            LOAD_CONST               8 ('Update task: ')
                    LOAD_FAST_BORROW         4 (task)
                    LOAD_CONST               9 ('title')
                    BINARY_OP               26 ([])
                    LOAD_CONST              10 (slice(None, 50, None))
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    BUILD_STRING             2
    
     678            LOAD_CONST              11 ('id')
                    LOAD_FAST_BORROW         0 (task_id)
                    LOAD_CONST              12 ('type')
                    LOAD_CONST              13 ('update')
                    LOAD_CONST              14 ('data')
                    LOAD_FAST_BORROW         7 (update_data)
                    BUILD_MAP                3
                    BUILD_LIST               1
    
     679            LOAD_FAST_BORROW_LOAD_FAST_BORROW 8 (task_id, pre_image)
                    BUILD_MAP                1
    
     676            LOAD_CONST              15 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               9 (bundle)
    
     682            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR               25 (update + NULL|self)
                    LOAD_CONST               2 ('tasks')
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 7 (task_id, update_data)
                    CALL                     3
                    POP_TOP
    
     683            LOAD_FAST_BORROW         3 (mark_applied)
                    PUSH_NULL
                    LOAD_FAST_BORROW         9 (bundle)
                    LOAD_CONST              11 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
     686            LOAD_CONST              16 ('success')
                    LOAD_CONST              17 (True)
    
     687            LOAD_CONST              18 ('task_id')
                    LOAD_FAST_BORROW         0 (task_id)
    
     688            LOAD_CONST              19 ('updated_fields')
                    LOAD_GLOBAL             27 (list + NULL)
                    LOAD_FAST_BORROW         7 (update_data)
                    LOAD_ATTR               23 (keys + NULL|self)
                    CALL                     0
                    CALL                     1
    
     689            LOAD_CONST              20 ('bundle_id')
                    LOAD_FAST_BORROW         9 (bundle)
                    LOAD_CONST              11 ('id')
                    BINARY_OP               26 ([])
    
     685            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L16:     SWAP                     2
                    POP_TOP
    
     668            SWAP                     3
                    STORE_FAST               6 (v)
                    STORE_FAST               5 (k)
                    RERAISE                  0
    
      --   L17:     SWAP                     2
                    POP_TOP
    
     675            SWAP                     2
                    STORE_FAST               5 (k)
                    RERAISE                  0
    
      --   L18:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L18 [0] lasti
      L3 to L5 -> L16 [3]
      L6 to L8 -> L16 [3]
      L8 to L10 -> L18 [0] lasti
      L10 to L12 -> L17 [2]
      L13 to L15 -> L17 [2]
      L15 to L18 -> L18 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/{task_id}/notes")
async def add_task_note(task_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:697
    
     697            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
     700            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST_BORROW         0 (task_id)
                    CALL                     2
                    STORE_FAST               2 (task)
    
     701            LOAD_FAST_BORROW         2 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
     702            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
     705    L2:     LOAD_FAST_BORROW         2 (task)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               4 ('notes')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L5)
            L3:     NOT_TAKEN
            L4:     POP_TOP
                    LOAD_CONST               5 ('')
            L5:     STORE_FAST               3 (existing_notes)
    
     706            LOAD_GLOBAL              6 (datetime)
                    LOAD_ATTR                8 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               11 (strftime + NULL|self)
                    LOAD_CONST               6 ('%Y-%m-%d %H:%M')
                    CALL                     1
                    STORE_FAST               4 (timestamp)
    
     707            LOAD_CONST               7 ('[')
                    LOAD_FAST_BORROW         4 (timestamp)
                    FORMAT_SIMPLE
                    LOAD_CONST               8 ('] ')
                    LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (note)
                    FORMAT_SIMPLE
                    BUILD_STRING             4
                    STORE_FAST               5 (new_note)
    
     709            LOAD_FAST_BORROW         3 (existing_notes)
                    TO_BOOL
                    POP_JUMP_IF_FALSE        9 (to L8)
            L6:     NOT_TAKEN
    
     710    L7:     LOAD_FAST_BORROW         3 (existing_notes)
                    FORMAT_SIMPLE
                    LOAD_CONST               9 ('\n\n')
                    LOAD_FAST_BORROW         5 (new_note)
                    FORMAT_SIMPLE
                    BUILD_STRING             3
                    STORE_FAST               6 (updated_notes)
                    JUMP_FORWARD             2 (to L9)
    
     712    L8:     LOAD_FAST                5 (new_note)
                    STORE_FAST               6 (updated_notes)
    
     714    L9:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               15 (update + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST_BORROW         0 (task_id)
    
     715            LOAD_CONST               4 ('notes')
                    LOAD_FAST_BORROW         6 (updated_notes)
    
     716            LOAD_CONST              10 ('updated_at')
                    LOAD_GLOBAL              6 (datetime)
                    LOAD_ATTR                8 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               17 (isoformat + NULL|self)
                    CALL                     0
    
     714            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
     720            LOAD_CONST              11 ('success')
                    LOAD_CONST              12 (True)
    
     721            LOAD_CONST              13 ('task_id')
                    LOAD_FAST_BORROW         0 (task_id)
    
     722            LOAD_CONST              14 ('note_added')
                    LOAD_FAST_BORROW         5 (new_note)
    
     719            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L10:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L10 [0] lasti
      L4 to L6 -> L10 [0] lasti
      L7 to L10 -> L10 [0] lasti
    """
    raise NotImplementedError

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:726
    
     726           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     729           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               1 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     2
                   STORE_FAST               1 (task)
    
     730           LOAD_FAST_BORROW         1 (task)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
     731           LOAD_GLOBAL              5 (HTTPException + NULL)
                   LOAD_CONST               2 (404)
                   LOAD_CONST               3 ('Task not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
     733   L2:     LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                7 (update + NULL|self)
                   LOAD_CONST               1 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
    
     734           LOAD_CONST               4 ('status')
                   LOAD_CONST               5 ('deleted')
    
     735           LOAD_CONST               6 ('updated_at')
                   LOAD_GLOBAL              8 (datetime)
                   LOAD_ATTR               10 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               13 (isoformat + NULL|self)
                   CALL                     0
    
     733           BUILD_MAP                2
                   CALL                     3
                   POP_TOP
    
     738           LOAD_CONST               7 ('success')
                   LOAD_CONST               8 (True)
                   LOAD_CONST               9 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/{task_id}/delegate")
async def delegate_task(task_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:756
    
     756           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     759           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DelegationHandler',))
                   IMPORT_NAME              0 (lib.executor.handlers.delegation)
                   IMPORT_FROM              1 (DelegationHandler)
                   STORE_FAST               2 (DelegationHandler)
                   POP_TOP
    
     761           LOAD_GLOBAL              4 (store)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST               2 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     2
                   STORE_FAST               3 (task)
    
     762           LOAD_FAST_BORROW         3 (task)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
     763           LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST               3 (404)
                   LOAD_CONST               4 ('Task not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
     765   L2:     LOAD_FAST_BORROW         2 (DelegationHandler)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               4 (handler)
    
     766           LOAD_FAST                4 (handler)
                   LOAD_ATTR               11 (execute + NULL|self)
    
     767           LOAD_CONST               5 ('action_type')
                   LOAD_CONST               6 ('delegate')
    
     768           LOAD_CONST               7 ('task_id')
                   LOAD_FAST                0 (task_id)
    
     769           LOAD_CONST               8 ('data')
    
     770           LOAD_CONST               9 ('delegate_to')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (delegate_to)
    
     771           LOAD_CONST              10 ('message')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               14 (message)
    
     772           LOAD_CONST              11 ('due_date')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               16 (due_date)
                   COPY                     1
                   TO_BOOL
                   POP_JUMP_IF_TRUE        18 (to L5)
           L3:     NOT_TAKEN
           L4:     POP_TOP
                   LOAD_FAST_BORROW         3 (task)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              11 ('due_date')
                   CALL                     1
    
     769   L5:     BUILD_MAP                3
    
     766           BUILD_MAP                3
                   CALL                     1
                   STORE_FAST               5 (result)
    
     776           LOAD_FAST_BORROW         5 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              12 ('success')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE       19 (to L8)
           L6:     NOT_TAKEN
    
     778   L7:     LOAD_CONST              12 ('success')
                   LOAD_CONST              13 (True)
    
     779           LOAD_CONST               7 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
    
     780           LOAD_CONST              14 ('delegated_to')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (delegate_to)
    
     777           BUILD_MAP                3
                   RETURN_VALUE
    
     783   L8:     LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST              15 (500)
                   LOAD_FAST_BORROW         5 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              16 ('error')
                   LOAD_CONST              17 ('Delegation failed')
                   CALL                     2
                   CALL                     2
                   RAISE_VARARGS            1
    
      --   L9:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L9 [0] lasti
      L4 to L6 -> L9 [0] lasti
      L7 to L9 -> L9 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/{task_id}/escalate")
async def escalate_task(task_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:786
    
     786           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     789           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DelegationHandler',))
                   IMPORT_NAME              0 (lib.executor.handlers.delegation)
                   IMPORT_FROM              1 (DelegationHandler)
                   STORE_FAST               2 (DelegationHandler)
                   POP_TOP
    
     791           LOAD_GLOBAL              4 (store)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST               2 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     2
                   STORE_FAST               3 (task)
    
     792           LOAD_FAST_BORROW         3 (task)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
     793           LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST               3 (404)
                   LOAD_CONST               4 ('Task not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
     795   L2:     LOAD_FAST_BORROW         2 (DelegationHandler)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               4 (handler)
    
     796           LOAD_FAST_BORROW         4 (handler)
                   LOAD_ATTR               11 (execute + NULL|self)
    
     797           LOAD_CONST               5 ('action_type')
                   LOAD_CONST               6 ('escalate')
    
     798           LOAD_CONST               7 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
    
     799           LOAD_CONST               8 ('data')
    
     800           LOAD_CONST               9 ('reason')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (reason)
    
     801           LOAD_CONST              10 ('escalate_to')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               14 (escalate_to)
    
     799           BUILD_MAP                2
    
     796           BUILD_MAP                3
                   CALL                     1
                   STORE_FAST               5 (result)
    
     805           LOAD_FAST_BORROW         5 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              11 ('success')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE        9 (to L5)
           L3:     NOT_TAKEN
    
     806   L4:     LOAD_CONST              11 ('success')
                   LOAD_CONST              12 (True)
                   LOAD_CONST               7 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
                   LOAD_CONST              13 ('escalated')
                   LOAD_CONST              12 (True)
                   BUILD_MAP                3
                   RETURN_VALUE
    
     808   L5:     LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST              14 (500)
                   LOAD_FAST_BORROW         5 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              15 ('error')
                   LOAD_CONST              16 ('Escalation failed')
                   CALL                     2
                   CALL                     2
                   RAISE_VARARGS            1
    
      --   L6:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L6 [0] lasti
      L4 to L6 -> L6 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/{task_id}/recall")
async def recall_task(task_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:811
    
     811           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
     814           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DelegationHandler',))
                   IMPORT_NAME              0 (lib.executor.handlers.delegation)
                   IMPORT_FROM              1 (DelegationHandler)
                   STORE_FAST               1 (DelegationHandler)
                   POP_TOP
    
     816           LOAD_GLOBAL              4 (store)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST               2 ('tasks')
                   LOAD_FAST_BORROW         0 (task_id)
                   CALL                     2
                   STORE_FAST               2 (task)
    
     817           LOAD_FAST_BORROW         2 (task)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
     818           LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST               3 (404)
                   LOAD_CONST               4 ('Task not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
     820   L2:     LOAD_FAST_BORROW         2 (task)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST               5 ('delegated_by')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L5)
           L3:     NOT_TAKEN
    
     821   L4:     LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST               6 (400)
                   LOAD_CONST               7 ('Task was not delegated')
                   CALL                     2
                   RAISE_VARARGS            1
    
     823   L5:     LOAD_FAST_BORROW         1 (DelegationHandler)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (handler)
    
     824           LOAD_FAST_BORROW         3 (handler)
                   LOAD_ATTR               11 (execute + NULL|self)
    
     825           LOAD_CONST               8 ('action_type')
                   LOAD_CONST               9 ('recall')
    
     826           LOAD_CONST              10 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
    
     827           LOAD_CONST              11 ('data')
                   BUILD_MAP                0
    
     824           BUILD_MAP                3
                   CALL                     1
                   STORE_FAST               4 (result)
    
     830           LOAD_FAST_BORROW         4 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              12 ('success')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE        9 (to L8)
           L6:     NOT_TAKEN
    
     831   L7:     LOAD_CONST              12 ('success')
                   LOAD_CONST              13 (True)
                   LOAD_CONST              10 ('task_id')
                   LOAD_FAST_BORROW         0 (task_id)
                   LOAD_CONST              14 ('recalled')
                   LOAD_CONST              13 (True)
                   BUILD_MAP                3
                   RETURN_VALUE
    
     833   L8:     LOAD_GLOBAL              9 (HTTPException + NULL)
                   LOAD_CONST              15 (500)
                   LOAD_FAST_BORROW         4 (result)
                   LOAD_ATTR                7 (get + NULL|self)
                   LOAD_CONST              16 ('error')
                   LOAD_CONST              17 ('Recall failed')
                   CALL                     2
                   CALL                     2
                   RAISE_VARARGS            1
    
      --   L9:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L9 [0] lasti
      L4 to L6 -> L9 [0] lasti
      L7 to L9 -> L9 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/delegations")
async def get_delegations():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:836
    
     836            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
     839            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT * FROM tasks \n        WHERE delegated_by IS NOT NULL AND delegated_by != '' AND status = 'pending'\n        ORDER BY delegated_at DESC\n    ")
                    CALL                     1
                    STORE_FAST               0 (delegated_by_me)
    
     845            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               2 ("\n        SELECT * FROM tasks \n        WHERE assignee = 'me' AND delegated_by IS NOT NULL AND status = 'pending'\n        ORDER BY due_date ASC\n    ")
                    CALL                     1
                    STORE_FAST               1 (delegated_to_me)
    
     852            LOAD_CONST               3 ('delegated_by_me')
                    LOAD_FAST_BORROW         0 (delegated_by_me)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                14 (to L4)
                    STORE_FAST               2 (t)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         2 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     SWAP                     2
                    STORE_FAST               2 (t)
    
     853            LOAD_CONST               4 ('delegated_to_me')
                    LOAD_FAST_BORROW         1 (delegated_to_me)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                14 (to L8)
                    STORE_FAST               2 (t)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         2 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               2 (t)
    
     854            LOAD_CONST               5 ('total')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         0 (delegated_by_me)
                    CALL                     1
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         1 (delegated_to_me)
                    CALL                     1
                    BINARY_OP                0 (+)
    
     851            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
     852            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L11:     SWAP                     2
                    POP_TOP
    
     853            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L12:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L12 [0] lasti
      L2 to L5 -> L10 [3]
      L5 to L6 -> L12 [0] lasti
      L6 to L9 -> L11 [5]
      L9 to L12 -> L12 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/data-quality")
async def get_data_quality():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:862
    
     862            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
     868            LOAD_GLOBAL              0 (datetime)
                    LOAD_ATTR                2 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR                5 (strftime + NULL|self)
                    LOAD_CONST               1 ('%Y-%m-%d')
                    CALL                     1
                    STORE_FAST               0 (today)
    
     871            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (query + NULL|self)
                    LOAD_CONST               2 ("\n        SELECT id, title, due_date, assignee, project, priority\n        FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n          AND due_date IS NOT NULL\n          AND date(due_date) < date('now', '-14 days')\n        ORDER BY due_date ASC\n        LIMIT 100\n    ")
                    CALL                     1
                    STORE_FAST               1 (stale_tasks)
    
     882            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (query + NULL|self)
                    LOAD_CONST               3 ("\n        SELECT id, title, due_date, assignee, project\n        FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n          AND due_date IS NOT NULL\n          AND date(due_date) < date('now', '-30 days')\n        ORDER BY due_date ASC\n        LIMIT 100\n    ")
                    CALL                     1
                    STORE_FAST               2 (ancient_tasks)
    
     893            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (query + NULL|self)
                    LOAD_CONST               4 ("\n        SELECT id, title, due_date, updated_at, assignee\n        FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n          AND (updated_at IS NULL OR date(updated_at) < date('now', '-30 days'))\n        LIMIT 100\n    ")
                    CALL                     1
                    STORE_FAST               3 (inactive_tasks)
    
     902            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (query + NULL|self)
                    LOAD_CONST               5 ("\n        SELECT \n            CASE \n                WHEN priority >= 80 THEN 'critical'\n                WHEN priority >= 60 THEN 'high'\n                WHEN priority >= 40 THEN 'medium'\n                ELSE 'low'\n            END as level,\n            COUNT(*) as count\n        FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n        GROUP BY level\n    ")
                    CALL                     1
                    STORE_FAST               4 (priority_dist)
    
     915            LOAD_FAST_BORROW         4 (priority_dist)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (r)
                    SWAP                     2
            L2:     BUILD_MAP                0
                    SWAP                     2
            L3:     FOR_ITER                19 (to L4)
                    STORE_FAST_LOAD_FAST    85 (r, r)
                    LOAD_CONST               6 ('level')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW         5 (r)
                    LOAD_CONST               7 ('count')
                    BINARY_OP               26 ([])
                    MAP_ADD                  2
                    JUMP_BACKWARD           21 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     STORE_FAST               6 (priority_by_level)
                    STORE_FAST               5 (r)
    
     918            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (query + NULL|self)
                    LOAD_CONST               8 ("\n        SELECT \n            CASE \n                WHEN due_date IS NULL THEN 'no_date'\n                WHEN date(due_date) < date('now', '-30 days') THEN 'ancient'\n                WHEN date(due_date) < date('now', '-14 days') THEN 'stale'\n                WHEN date(due_date) < date('now') THEN 'overdue'\n                WHEN date(due_date) = date('now') THEN 'today'\n                WHEN date(due_date) <= date('now', '+7 days') THEN 'this_week'\n                ELSE 'future'\n            END as period,\n            COUNT(*) as count\n        FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n        GROUP BY period\n    ")
                    CALL                     1
                    STORE_FAST               7 (due_dist)
    
     934            LOAD_FAST_BORROW         7 (due_dist)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (r)
                    SWAP                     2
            L6:     BUILD_MAP                0
                    SWAP                     2
            L7:     FOR_ITER                19 (to L8)
                    STORE_FAST_LOAD_FAST    85 (r, r)
                    LOAD_CONST               9 ('period')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW         5 (r)
                    LOAD_CONST               7 ('count')
                    BINARY_OP               26 ([])
                    MAP_ADD                  2
                    JUMP_BACKWARD           21 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     STORE_FAST               8 (due_by_period)
                    STORE_FAST               5 (r)
    
     937            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR               11 (count + NULL|self)
                    LOAD_CONST              10 ('tasks')
                    LOAD_CONST              11 ("status NOT IN ('completed', 'done', 'cancelled', 'deleted')")
                    CALL                     2
                    STORE_FAST               9 (total_active)
    
     940            LOAD_FAST_BORROW         8 (due_by_period)
                    LOAD_ATTR               13 (get + NULL|self)
                    LOAD_CONST              12 ('ancient')
                    LOAD_SMALL_INT           0
                    CALL                     2
                    LOAD_FAST_BORROW         8 (due_by_period)
                    LOAD_ATTR               13 (get + NULL|self)
                    LOAD_CONST              13 ('stale')
                    LOAD_SMALL_INT           0
                    CALL                     2
                    BINARY_OP                0 (+)
                    LOAD_GLOBAL             15 (max + NULL)
                    LOAD_SMALL_INT           1
                    LOAD_FAST_BORROW         9 (total_active)
                    CALL                     2
                    BINARY_OP               11 (/)
                    STORE_FAST              10 (stale_ratio)
    
     941            LOAD_FAST_BORROW         6 (priority_by_level)
                    LOAD_ATTR               13 (get + NULL|self)
                    LOAD_CONST              14 ('critical')
                    LOAD_SMALL_INT           0
                    CALL                     2
                    LOAD_GLOBAL             15 (max + NULL)
                    LOAD_SMALL_INT           1
                    LOAD_FAST_BORROW         9 (total_active)
                    CALL                     2
                    BINARY_OP               11 (/)
                    STORE_FAST              11 (priority_inflation)
    
     943            LOAD_GLOBAL             15 (max + NULL)
                    LOAD_SMALL_INT           0
                    LOAD_GLOBAL             17 (min + NULL)
                    LOAD_SMALL_INT         100
                    LOAD_GLOBAL             19 (int + NULL)
                    LOAD_SMALL_INT         100
                    LOAD_FAST_BORROW        10 (stale_ratio)
                    LOAD_SMALL_INT          50
                    BINARY_OP                5 (*)
                    BINARY_OP               10 (-)
                    LOAD_FAST_BORROW        11 (priority_inflation)
                    LOAD_SMALL_INT          30
                    BINARY_OP                5 (*)
                    BINARY_OP               10 (-)
                    CALL                     1
                    CALL                     2
                    CALL                     2
                    STORE_FAST              12 (health_score)
    
     946            LOAD_CONST              15 ('health_score')
                    LOAD_FAST               12 (health_score)
    
     947            LOAD_CONST              16 ('total_active_tasks')
                    LOAD_FAST                9 (total_active)
    
     948            LOAD_CONST              17 ('issues')
    
     949            LOAD_CONST              18 ('stale_tasks')
    
     950            LOAD_CONST               7 ('count')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         1 (stale_tasks)
                    CALL                     1
    
     951            LOAD_CONST              19 ('items')
                    LOAD_FAST_BORROW         1 (stale_tasks)
                    LOAD_CONST              20 (slice(None, 20, None))
                    BINARY_OP               26 ([])
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     13 (t)
                    SWAP                     2
           L10:     BUILD_LIST               0
                    SWAP                     2
           L11:     FOR_ITER                14 (to L12)
                    STORE_FAST              13 (t)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW        13 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L11)
           L12:     END_FOR
                    POP_ITER
           L13:     SWAP                     2
                    STORE_FAST              13 (t)
    
     949            BUILD_MAP                2
    
     953            LOAD_CONST              21 ('ancient_tasks')
    
     954            LOAD_CONST               7 ('count')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         2 (ancient_tasks)
                    CALL                     1
    
     955            LOAD_CONST              19 ('items')
                    LOAD_FAST_BORROW         2 (ancient_tasks)
                    LOAD_CONST              20 (slice(None, 20, None))
                    BINARY_OP               26 ([])
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     13 (t)
                    SWAP                     2
           L14:     BUILD_LIST               0
                    SWAP                     2
           L15:     FOR_ITER                14 (to L16)
                    STORE_FAST              13 (t)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW        13 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L15)
           L16:     END_FOR
                    POP_ITER
           L17:     SWAP                     2
                    STORE_FAST              13 (t)
    
     953            BUILD_MAP                2
    
     957            LOAD_CONST              22 ('inactive_tasks')
    
     958            LOAD_CONST               7 ('count')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         3 (inactive_tasks)
                    CALL                     1
    
     959            LOAD_CONST              19 ('items')
                    LOAD_FAST_BORROW         3 (inactive_tasks)
                    LOAD_CONST              20 (slice(None, 20, None))
                    BINARY_OP               26 ([])
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     13 (t)
                    SWAP                     2
           L18:     BUILD_LIST               0
                    SWAP                     2
           L19:     FOR_ITER                14 (to L20)
                    STORE_FAST              13 (t)
                    LOAD_GLOBAL             23 (dict + NULL)
                    LOAD_FAST_BORROW        13 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L19)
           L20:     END_FOR
                    POP_ITER
           L21:     SWAP                     2
                    STORE_FAST              13 (t)
    
     957            BUILD_MAP                2
    
     948            BUILD_MAP                3
    
     962            LOAD_CONST              23 ('metrics')
    
     963            LOAD_CONST              24 ('priority_distribution')
                    LOAD_FAST_BORROW         6 (priority_by_level)
    
     964            LOAD_CONST              25 ('due_distribution')
                    LOAD_FAST_BORROW         8 (due_by_period)
    
     965            LOAD_CONST              26 ('priority_inflation_ratio')
                    LOAD_GLOBAL             25 (round + NULL)
                    LOAD_FAST_BORROW        11 (priority_inflation)
                    LOAD_SMALL_INT           2
                    CALL                     2
    
     966            LOAD_CONST              27 ('stale_ratio')
                    LOAD_GLOBAL             25 (round + NULL)
                    LOAD_FAST_BORROW        10 (stale_ratio)
                    LOAD_SMALL_INT           2
                    CALL                     2
    
     962            BUILD_MAP                4
    
     968            LOAD_CONST              28 ('suggestions')
                    LOAD_GLOBAL             27 (_get_cleanup_suggestions + NULL)
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 134 (due_by_period, priority_by_level)
                    LOAD_FAST_BORROW         9 (total_active)
                    CALL                     3
    
     945            BUILD_MAP                5
                    RETURN_VALUE
    
      --   L22:     SWAP                     2
                    POP_TOP
    
     915            SWAP                     2
                    STORE_FAST               5 (r)
                    RERAISE                  0
    
      --   L23:     SWAP                     2
                    POP_TOP
    
     934            SWAP                     2
                    STORE_FAST               5 (r)
                    RERAISE                  0
    
      --   L24:     SWAP                     2
                    POP_TOP
    
     951            SWAP                     2
                    STORE_FAST              13 (t)
                    RERAISE                  0
    
      --   L25:     SWAP                     2
                    POP_TOP
    
     955            SWAP                     2
                    STORE_FAST              13 (t)
                    RERAISE                  0
    
      --   L26:     SWAP                     2
                    POP_TOP
    
     959            SWAP                     2
                    STORE_FAST              13 (t)
                    RERAISE                  0
    
      --   L27:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L27 [0] lasti
      L2 to L5 -> L22 [2]
      L5 to L6 -> L27 [0] lasti
      L6 to L9 -> L23 [2]
      L9 to L10 -> L27 [0] lasti
      L10 to L13 -> L24 [11]
      L13 to L14 -> L27 [0] lasti
      L14 to L17 -> L25 [13]
      L17 to L18 -> L27 [0] lasti
      L18 to L21 -> L26 [15]
      L21 to L27 -> L27 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/data-quality/cleanup/ancient")
async def cleanup_ancient_tasks(confirm):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1013
    
    1013            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1016            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT id, title FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n          AND due_date IS NOT NULL\n          AND date(due_date) < date('now', '-30 days')\n    ")
                    CALL                     1
                    STORE_FAST               1 (tasks)
    
    1023            LOAD_FAST_BORROW         0 (confirm)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        67 (to L6)
                    NOT_TAKEN
    
    1025            LOAD_CONST               2 ('preview')
                    LOAD_CONST               3 (True)
    
    1026            LOAD_CONST               4 ('count')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
    
    1027            LOAD_CONST               5 ('message')
                    LOAD_CONST               6 ('This will archive ')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST               7 (' ancient tasks')
                    BUILD_STRING             3
    
    1028            LOAD_CONST               8 ('sample')
                    LOAD_FAST_BORROW         1 (tasks)
                    LOAD_CONST               9 (slice(None, 10, None))
                    BINARY_OP               26 ([])
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                14 (to L4)
                    STORE_FAST               2 (t)
                    LOAD_GLOBAL              7 (dict + NULL)
                    LOAD_FAST_BORROW         2 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1029            LOAD_CONST              10 ('confirm_endpoint')
                    LOAD_CONST              11 ('/api/data-quality/cleanup/ancient?confirm=true')
    
    1024            BUILD_MAP                5
                    RETURN_VALUE
    
    1033    L6:     LOAD_SMALL_INT           0
                    LOAD_CONST              12 (('create_task_bundle', 'mark_applied'))
                    IMPORT_NAME              4 (lib.change_bundles)
                    IMPORT_FROM              5 (create_task_bundle)
                    STORE_FAST               3 (create_task_bundle)
                    IMPORT_FROM              6 (mark_applied)
                    STORE_FAST               4 (mark_applied)
                    POP_TOP
    
    1035            LOAD_FAST                3 (create_task_bundle)
                    PUSH_NULL
    
    1036            LOAD_CONST              13 ('Bulk archive ')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST               7 (' ancient tasks')
                    BUILD_STRING             3
    
    1037            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L7:     BUILD_LIST               0
                    SWAP                     2
            L8:     FOR_ITER                16 (to L9)
                    STORE_FAST               2 (t)
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    LOAD_CONST              15 ('type')
                    LOAD_CONST              16 ('archive')
                    BUILD_MAP                2
                    LIST_APPEND              2
                    JUMP_BACKWARD           18 (to L8)
            L9:     END_FOR
                    POP_ITER
           L10:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1038            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
           L11:     BUILD_MAP                0
                    SWAP                     2
           L12:     FOR_ITER                14 (to L13)
                    STORE_FAST_LOAD_FAST    34 (t, t)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    LOAD_CONST              17 ('status')
                    LOAD_CONST              18 ('pending')
                    BUILD_MAP                1
                    MAP_ADD                  2
                    JUMP_BACKWARD           16 (to L12)
           L13:     END_FOR
                    POP_ITER
           L14:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1035            LOAD_CONST              19 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               5 (bundle)
    
    1042            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
           L15:     FOR_ITER                70 (to L16)
                    STORE_FAST               6 (task)
    
    1043            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               15 (update + NULL|self)
                    LOAD_CONST              20 ('tasks')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
    
    1044            LOAD_CONST              17 ('status')
                    LOAD_CONST              21 ('archived')
    
    1045            LOAD_CONST              22 ('updated_at')
                    LOAD_GLOBAL             16 (datetime)
                    LOAD_ATTR               18 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               21 (isoformat + NULL|self)
                    CALL                     0
    
    1043            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
                    JUMP_BACKWARD           72 (to L15)
    
    1042   L16:     END_FOR
                    POP_ITER
    
    1048            LOAD_FAST_BORROW         4 (mark_applied)
                    PUSH_NULL
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1051            LOAD_CONST              23 ('success')
                    LOAD_CONST               3 (True)
    
    1052            LOAD_CONST              24 ('archived_count')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
    
    1053            LOAD_CONST              25 ('bundle_id')
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
    
    1054            LOAD_CONST               5 ('message')
                    LOAD_CONST              26 ('Archived ')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST              27 (' ancient tasks. Use bundle ')
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    LOAD_CONST              28 (' to rollback.')
                    BUILD_STRING             5
    
    1050            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L17:     SWAP                     2
                    POP_TOP
    
    1028            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L18:     SWAP                     2
                    POP_TOP
    
    1037            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L19:     SWAP                     2
                    POP_TOP
    
    1038            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L20:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L20 [0] lasti
      L2 to L5 -> L17 [9]
      L5 to L7 -> L20 [0] lasti
      L7 to L10 -> L18 [5]
      L10 to L11 -> L20 [0] lasti
      L11 to L14 -> L19 [6]
      L14 to L20 -> L20 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/data-quality/cleanup/stale")
async def cleanup_stale_tasks(confirm):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1058
    
    1058            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1061            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT id, title FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n          AND due_date IS NOT NULL\n          AND date(due_date) < date('now', '-14 days')\n          AND date(due_date) >= date('now', '-30 days')\n    ")
                    CALL                     1
                    STORE_FAST               1 (tasks)
    
    1069            LOAD_FAST_BORROW         0 (confirm)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        67 (to L6)
                    NOT_TAKEN
    
    1071            LOAD_CONST               2 ('preview')
                    LOAD_CONST               3 (True)
    
    1072            LOAD_CONST               4 ('count')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
    
    1073            LOAD_CONST               5 ('message')
                    LOAD_CONST               6 ('This will archive ')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST               7 (' stale tasks (14-30 days overdue)')
                    BUILD_STRING             3
    
    1074            LOAD_CONST               8 ('sample')
                    LOAD_FAST_BORROW         1 (tasks)
                    LOAD_CONST               9 (slice(None, 10, None))
                    BINARY_OP               26 ([])
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                14 (to L4)
                    STORE_FAST               2 (t)
                    LOAD_GLOBAL              7 (dict + NULL)
                    LOAD_FAST_BORROW         2 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1075            LOAD_CONST              10 ('confirm_endpoint')
                    LOAD_CONST              11 ('/api/data-quality/cleanup/stale?confirm=true')
    
    1070            BUILD_MAP                5
                    RETURN_VALUE
    
    1078    L6:     LOAD_SMALL_INT           0
                    LOAD_CONST              12 (('create_task_bundle', 'mark_applied'))
                    IMPORT_NAME              4 (lib.change_bundles)
                    IMPORT_FROM              5 (create_task_bundle)
                    STORE_FAST               3 (create_task_bundle)
                    IMPORT_FROM              6 (mark_applied)
                    STORE_FAST               4 (mark_applied)
                    POP_TOP
    
    1080            LOAD_FAST                3 (create_task_bundle)
                    PUSH_NULL
    
    1081            LOAD_CONST              13 ('Bulk archive ')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST              14 (' stale tasks')
                    BUILD_STRING             3
    
    1082            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L7:     BUILD_LIST               0
                    SWAP                     2
            L8:     FOR_ITER                16 (to L9)
                    STORE_FAST               2 (t)
                    LOAD_CONST              15 ('id')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    LOAD_CONST              16 ('type')
                    LOAD_CONST              17 ('archive')
                    BUILD_MAP                2
                    LIST_APPEND              2
                    JUMP_BACKWARD           18 (to L8)
            L9:     END_FOR
                    POP_ITER
           L10:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1083            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
           L11:     BUILD_MAP                0
                    SWAP                     2
           L12:     FOR_ITER                14 (to L13)
                    STORE_FAST_LOAD_FAST    34 (t, t)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    LOAD_CONST              18 ('status')
                    LOAD_CONST              19 ('pending')
                    BUILD_MAP                1
                    MAP_ADD                  2
                    JUMP_BACKWARD           16 (to L12)
           L13:     END_FOR
                    POP_ITER
           L14:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1080            LOAD_CONST              20 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               5 (bundle)
    
    1086            LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
           L15:     FOR_ITER                70 (to L16)
                    STORE_FAST               6 (task)
    
    1087            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               15 (update + NULL|self)
                    LOAD_CONST              21 ('tasks')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
    
    1088            LOAD_CONST              18 ('status')
                    LOAD_CONST              22 ('archived')
    
    1089            LOAD_CONST              23 ('updated_at')
                    LOAD_GLOBAL             16 (datetime)
                    LOAD_ATTR               18 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               21 (isoformat + NULL|self)
                    CALL                     0
    
    1087            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
                    JUMP_BACKWARD           72 (to L15)
    
    1086   L16:     END_FOR
                    POP_ITER
    
    1092            LOAD_FAST_BORROW         4 (mark_applied)
                    PUSH_NULL
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1095            LOAD_CONST              24 ('success')
                    LOAD_CONST               3 (True)
    
    1096            LOAD_CONST              25 ('archived_count')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
    
    1097            LOAD_CONST              26 ('bundle_id')
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
    
    1094            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L17:     SWAP                     2
                    POP_TOP
    
    1074            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L18:     SWAP                     2
                    POP_TOP
    
    1082            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L19:     SWAP                     2
                    POP_TOP
    
    1083            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L20:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L20 [0] lasti
      L2 to L5 -> L17 [9]
      L5 to L7 -> L20 [0] lasti
      L7 to L10 -> L18 [5]
      L10 to L11 -> L20 [0] lasti
      L11 to L14 -> L19 [6]
      L14 to L20 -> L20 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/data-quality/recalculate-priorities")
async def recalculate_priorities():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1101
    
    1101           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1110           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
                   LOAD_CONST               1 ("\n        SELECT * FROM tasks\n        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n    ")
                   CALL                     1
                   STORE_FAST               0 (tasks)
    
    1115           LOAD_GLOBAL              4 (datetime)
                   LOAD_ATTR                6 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                9 (date + NULL|self)
                   CALL                     0
                   STORE_FAST               1 (today)
    
    1116           LOAD_SMALL_INT           0
                   STORE_FAST               2 (updated)
    
    1118           LOAD_FAST_BORROW         0 (tasks)
                   GET_ITER
           L2:     FOR_ITER               142 (to L5)
                   STORE_FAST               3 (task)
    
    1119           LOAD_FAST_BORROW         3 (task)
                   LOAD_ATTR               11 (get + NULL|self)
                   LOAD_CONST               2 ('priority')
                   LOAD_SMALL_INT          50
                   CALL                     2
                   STORE_FAST               4 (old_priority)
    
    1120           LOAD_GLOBAL             13 (_calculate_realistic_priority + NULL)
                   LOAD_GLOBAL             15 (dict + NULL)
                   LOAD_FAST_BORROW         3 (task)
                   CALL                     1
                   LOAD_FAST_BORROW         1 (today)
                   CALL                     2
                   STORE_FAST               5 (new_priority)
    
    1122           LOAD_GLOBAL             17 (abs + NULL)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 84 (new_priority, old_priority)
                   BINARY_OP               10 (-)
                   CALL                     1
                   LOAD_SMALL_INT           5
                   COMPARE_OP             148 (bool(>))
           L3:     POP_JUMP_IF_TRUE         3 (to L4)
                   NOT_TAKEN
                   JUMP_BACKWARD           66 (to L2)
    
    1123   L4:     LOAD_GLOBAL              0 (store)
                   LOAD_ATTR               19 (update + NULL|self)
                   LOAD_CONST               3 ('tasks')
                   LOAD_FAST_BORROW         3 (task)
                   LOAD_CONST               4 ('id')
                   BINARY_OP               26 ([])
    
    1124           LOAD_CONST               2 ('priority')
                   LOAD_FAST_BORROW         5 (new_priority)
    
    1125           LOAD_CONST               5 ('updated_at')
                   LOAD_GLOBAL              4 (datetime)
                   LOAD_ATTR                6 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               21 (isoformat + NULL|self)
                   CALL                     0
    
    1123           BUILD_MAP                2
                   CALL                     3
                   POP_TOP
    
    1127           LOAD_FAST_BORROW         2 (updated)
                   LOAD_SMALL_INT           1
                   BINARY_OP               13 (+=)
                   STORE_FAST               2 (updated)
                   JUMP_BACKWARD          144 (to L2)
    
    1118   L5:     END_FOR
                   POP_ITER
    
    1130           LOAD_CONST               6 ('success')
                   LOAD_CONST               7 (True)
    
    1131           LOAD_CONST               8 ('tasks_updated')
                   LOAD_FAST_BORROW         2 (updated)
    
    1132           LOAD_CONST               9 ('total_tasks')
                   LOAD_GLOBAL             23 (len + NULL)
                   LOAD_FAST_BORROW         0 (tasks)
                   CALL                     1
    
    1133           LOAD_CONST              10 ('message')
                   LOAD_CONST              11 ('Recalculated priorities for ')
                   LOAD_FAST_BORROW         2 (updated)
                   FORMAT_SIMPLE
                   LOAD_CONST              12 (' tasks')
                   BUILD_STRING             3
    
    1129           BUILD_MAP                4
                   RETURN_VALUE
    
      --   L6:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L6 [0] lasti
      L4 to L6 -> L6 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/data-quality/preview/{cleanup_type}")
async def preview_cleanup(cleanup_type):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1194
    
    1194            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1197            LOAD_FAST_BORROW         0 (cleanup_type)
                    LOAD_CONST               1 ('ancient')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       23 (to L2)
                    NOT_TAKEN
    
    1198            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               2 ("\n            SELECT id, title, due_date, assignee, project\n            FROM tasks\n            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n              AND due_date IS NOT NULL\n              AND date(due_date) < date('now', '-30 days')\n            ORDER BY due_date ASC\n        ")
                    CALL                     1
                    STORE_FAST               1 (tasks)
                    JUMP_FORWARD            73 (to L5)
    
    1206    L2:     LOAD_FAST_BORROW         0 (cleanup_type)
                    LOAD_CONST               3 ('stale')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       23 (to L3)
                    NOT_TAKEN
    
    1207            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               4 ("\n            SELECT id, title, due_date, assignee, project\n            FROM tasks\n            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n              AND due_date IS NOT NULL\n              AND date(due_date) < date('now', '-14 days')\n              AND date(due_date) >= date('now', '-30 days')\n            ORDER BY due_date ASC\n        ")
                    CALL                     1
                    STORE_FAST               1 (tasks)
                    JUMP_FORWARD            44 (to L5)
    
    1216    L3:     LOAD_FAST_BORROW         0 (cleanup_type)
                    LOAD_CONST               5 ('no_date')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       23 (to L4)
                    NOT_TAKEN
    
    1217            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               6 ("\n            SELECT id, title, created_at, assignee, project\n            FROM tasks\n            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')\n              AND due_date IS NULL\n            ORDER BY created_at ASC\n        ")
                    CALL                     1
                    STORE_FAST               1 (tasks)
                    JUMP_FORWARD            15 (to L5)
    
    1225    L4:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               7 (400)
                    LOAD_CONST               8 ('Unknown cleanup type: ')
                    LOAD_FAST_BORROW         0 (cleanup_type)
                    FORMAT_SIMPLE
                    BUILD_STRING             2
                    CALL                     2
                    RAISE_VARARGS            1
    
    1228    L5:     LOAD_CONST               9 ('cleanup_type')
                    LOAD_FAST                0 (cleanup_type)
    
    1229            LOAD_CONST              10 ('count')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         1 (tasks)
                    CALL                     1
    
    1230            LOAD_CONST              11 ('items')
                    LOAD_FAST_BORROW         1 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                14 (to L8)
                    STORE_FAST               2 (t)
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         2 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               2 (t)
    
    1227            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
    1230            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L11:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L6 -> L11 [0] lasti
      L6 to L9 -> L10 [7]
      L9 to L11 -> L11 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/team")
async def get_team():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1238
    
    1238           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1241           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    1242           LOAD_CONST               1 ('SELECT * FROM people WHERE is_internal = 1 ORDER BY name')
    
    1241           CALL                     1
                   STORE_FAST               0 (people)
    
    1245           BUILD_LIST               0
                   STORE_FAST               1 (team)
    
    1246           LOAD_FAST_BORROW         0 (people)
                   GET_ITER
           L2:     FOR_ITER                68 (to L3)
                   STORE_FAST               2 (person)
    
    1247           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                5 (count + NULL|self)
                   LOAD_CONST               2 ('tasks')
                   LOAD_CONST               3 ("assignee LIKE '%")
                   LOAD_FAST_BORROW         2 (person)
                   LOAD_CONST               4 ('name')
                   BINARY_OP               26 ([])
                   FORMAT_SIMPLE
                   LOAD_CONST               5 ("%' AND status != 'done'")
                   BUILD_STRING             3
                   CALL                     2
                   STORE_FAST               3 (task_count)
    
    1248           LOAD_FAST_BORROW         1 (team)
                   LOAD_ATTR                7 (append + NULL|self)
                   BUILD_MAP                0
    
    1249           LOAD_GLOBAL              9 (dict + NULL)
                   LOAD_FAST_BORROW         2 (person)
                   CALL                     1
    
    1248           DICT_UPDATE              1
    
    1250           LOAD_CONST               6 ('pending_tasks')
                   LOAD_FAST_BORROW         3 (task_count)
    
    1248           BUILD_MAP                1
                   DICT_UPDATE              1
                   CALL                     1
                   POP_TOP
                   JUMP_BACKWARD           70 (to L2)
    
    1246   L3:     END_FOR
                   POP_ITER
    
    1253           LOAD_CONST               7 ('members')
                   LOAD_FAST_BORROW         1 (team)
                   LOAD_CONST               8 ('total')
                   LOAD_GLOBAL             11 (len + NULL)
                   LOAD_FAST_BORROW         1 (team)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/projects")
async def get_projects(status, enrolled_only, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2863
    
    2863            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2866            LOAD_CONST               1 ('1=1')
                    BUILD_LIST               1
                    STORE_FAST               3 (conditions)
    
    2867            BUILD_LIST               0
                    STORE_FAST               4 (params)
    
    2869            LOAD_FAST_BORROW         1 (enrolled_only)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       19 (to L2)
                    NOT_TAKEN
    
    2870            LOAD_FAST_BORROW         3 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               2 ("enrollment_status = 'enrolled'")
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD            42 (to L5)
    
    2871    L2:     LOAD_FAST_BORROW         0 (status)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       35 (to L5)
            L3:     NOT_TAKEN
    
    2872    L4:     LOAD_FAST_BORROW         3 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               3 ('enrollment_status = ?')
                    CALL                     1
                    POP_TOP
    
    2873            LOAD_FAST_BORROW         4 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         0 (status)
                    CALL                     1
                    POP_TOP
    
    2875    L5:     LOAD_FAST_BORROW         4 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         2 (limit)
                    CALL                     1
                    POP_TOP
    
    2877            LOAD_GLOBAL              2 (store)
                    LOAD_ATTR                5 (query + NULL|self)
                    LOAD_CONST               4 ('\n        SELECT p.*, c.name as client_name, c.tier as client_tier\n        FROM projects p\n        LEFT JOIN clients c ON p.client_id = c.id\n        WHERE ')
    
    2881            LOAD_CONST               5 (' AND ')
                    LOAD_ATTR                7 (join + NULL|self)
                    LOAD_FAST_BORROW         3 (conditions)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST               6 ("\n        ORDER BY \n            CASE enrollment_status \n                WHEN 'enrolled' THEN 1 \n                WHEN 'candidate' THEN 2 \n                WHEN 'proposed' THEN 3 \n                ELSE 4 \n            END,\n            p.name\n        LIMIT ?\n    ")
    
    2877            BUILD_STRING             3
    
    2891            LOAD_FAST_BORROW         4 (params)
    
    2877            CALL                     2
                    STORE_FAST               5 (projects)
    
    2893            LOAD_CONST               7 ('items')
                    LOAD_FAST_BORROW         5 (projects)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      6 (p)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                14 (to L8)
                    STORE_FAST               6 (p)
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         6 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               6 (p)
                    LOAD_CONST               8 ('total')
                    LOAD_GLOBAL             11 (len + NULL)
                    LOAD_FAST_BORROW         5 (projects)
                    CALL                     1
                    BUILD_MAP                2
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
    2893            SWAP                     2
                    STORE_FAST               6 (p)
                    RERAISE                  0
    
      --   L11:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L11 [0] lasti
      L4 to L6 -> L11 [0] lasti
      L6 to L9 -> L10 [3]
      L9 to L11 -> L11 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/calendar")
async def api_calendar(start, end, view):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1290
    
    1290            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1297            LOAD_FAST                0 (start)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        50 (to L2)
                    NOT_TAKEN
                    POP_TOP
                    LOAD_GLOBAL              0 (datetime)
                    LOAD_ATTR                2 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR                5 (date + NULL|self)
                    CALL                     0
                    LOAD_ATTR                7 (isoformat + NULL|self)
                    CALL                     0
            L2:     STORE_FAST               3 (sd)
    
    1298            LOAD_FAST                1 (end)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        68 (to L5)
            L3:     NOT_TAKEN
            L4:     POP_TOP
                    LOAD_GLOBAL              0 (datetime)
                    LOAD_ATTR                8 (fromisoformat)
                    PUSH_NULL
                    LOAD_FAST_BORROW         3 (sd)
                    CALL                     1
                    LOAD_ATTR                5 (date + NULL|self)
                    CALL                     0
                    LOAD_GLOBAL             11 (timedelta + NULL)
                    LOAD_SMALL_INT          14
                    LOAD_CONST               1 (('days',))
                    CALL_KW                  1
                    BINARY_OP                0 (+)
                    LOAD_ATTR                7 (isoformat + NULL|self)
                    CALL                     0
            L5:     STORE_FAST               4 (ed)
    
    1299            LOAD_GLOBAL             12 (store)
                    LOAD_ATTR               15 (query + NULL|self)
    
    1300            LOAD_CONST               2 ('SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time')
    
    1301            LOAD_FAST_BORROW_LOAD_FAST_BORROW 52 (sd, ed)
                    BUILD_LIST               2
    
    1299            CALL                     2
                    STORE_FAST               5 (events)
    
    1305            LOAD_CONST               3 ('range')
                    LOAD_CONST               4 ('start')
                    LOAD_FAST_BORROW         3 (sd)
                    LOAD_CONST               5 ('end')
                    LOAD_FAST_BORROW         4 (ed)
                    BUILD_MAP                2
    
    1306            LOAD_CONST               6 ('events')
                    LOAD_FAST_BORROW         5 (events)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      6 (e)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                14 (to L8)
                    STORE_FAST               6 (e)
                    LOAD_GLOBAL             17 (dict + NULL)
                    LOAD_FAST_BORROW         6 (e)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               6 (e)
    
    1307            LOAD_CONST               7 ('analysis')
                    BUILD_MAP                0
    
    1308            LOAD_CONST               8 ('conflicts')
                    BUILD_LIST               0
    
    1304            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
    1306            SWAP                     2
                    STORE_FAST               6 (e)
                    RERAISE                  0
    
      --   L11:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L11 [0] lasti
      L4 to L6 -> L11 [0] lasti
      L6 to L9 -> L10 [5]
      L9 to L11 -> L11 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/delegations")
async def api_delegations():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1311
    
    1311           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1314           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    1315           LOAD_CONST               1 ('SELECT id, title, delegated_by, delegated_at FROM tasks WHERE delegated_by IS NOT NULL ORDER BY delegated_at DESC')
    
    1314           CALL                     1
                   STORE_FAST               0 (delegs)
    
    1317           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         0 (delegs)
                   GET_ITER
                   LOAD_FAST_AND_CLEAR      1 (d)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
           L3:     FOR_ITER                14 (to L4)
                   STORE_FAST               1 (d)
                   LOAD_GLOBAL              5 (dict + NULL)
                   LOAD_FAST_BORROW         1 (d)
                   CALL                     1
                   LIST_APPEND              2
                   JUMP_BACKWARD           16 (to L3)
           L4:     END_FOR
                   POP_ITER
           L5:     SWAP                     2
                   STORE_FAST               1 (d)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              7 (len + NULL)
                   LOAD_FAST_BORROW         0 (delegs)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
    1317           SWAP                     2
                   STORE_FAST               1 (d)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/inbox")
async def api_inbox(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1319
    
    1319           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1322           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    1323           LOAD_CONST               1 ('SELECT * FROM communications WHERE requires_response = 1 AND processed = 0 ORDER BY created_at DESC LIMIT ?')
                   LOAD_FAST_BORROW         0 (limit)
                   BUILD_LIST               1
    
    1322           CALL                     2
                   STORE_FAST               1 (comms)
    
    1325           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         1 (comms)
                   GET_ITER
                   LOAD_FAST_AND_CLEAR      2 (c)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
           L3:     FOR_ITER                14 (to L4)
                   STORE_FAST               2 (c)
                   LOAD_GLOBAL              5 (dict + NULL)
                   LOAD_FAST_BORROW         2 (c)
                   CALL                     1
                   LIST_APPEND              2
                   JUMP_BACKWARD           16 (to L3)
           L4:     END_FOR
                   POP_ITER
           L5:     SWAP                     2
                   STORE_FAST               2 (c)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                7 (count + NULL|self)
                   LOAD_CONST               4 ('communications')
                   LOAD_CONST               5 ('requires_response = 1 AND processed = 0')
                   CALL                     2
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
    1325           SWAP                     2
                   STORE_FAST               2 (c)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/insights")
async def api_insights(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1327
    
    1327           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1330           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    1331           LOAD_CONST               1 ('SELECT * FROM insights ORDER BY created_at DESC LIMIT ?')
                   LOAD_FAST_BORROW         0 (limit)
                   BUILD_LIST               1
    
    1330           CALL                     2
                   STORE_FAST               1 (ins)
    
    1333           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         1 (ins)
                   GET_ITER
                   LOAD_FAST_AND_CLEAR      2 (i)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
           L3:     FOR_ITER                14 (to L4)
                   STORE_FAST               2 (i)
                   LOAD_GLOBAL              5 (dict + NULL)
                   LOAD_FAST_BORROW         2 (i)
                   CALL                     1
                   LIST_APPEND              2
                   JUMP_BACKWARD           16 (to L3)
           L4:     END_FOR
                   POP_ITER
           L5:     SWAP                     2
                   STORE_FAST               2 (i)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                7 (count + NULL|self)
                   LOAD_CONST               4 ('insights')
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
    1333           SWAP                     2
                   STORE_FAST               2 (i)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/decisions")
async def api_decisions(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1335
    
    1335           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1338           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    1339           LOAD_CONST               1 ('SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?')
                   LOAD_FAST_BORROW         0 (limit)
                   BUILD_LIST               1
    
    1338           CALL                     2
                   STORE_FAST               1 (decs)
    
    1341           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         1 (decs)
                   GET_ITER
                   LOAD_FAST_AND_CLEAR      2 (d)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
           L3:     FOR_ITER                14 (to L4)
                   STORE_FAST               2 (d)
                   LOAD_GLOBAL              5 (dict + NULL)
                   LOAD_FAST_BORROW         2 (d)
                   CALL                     1
                   LIST_APPEND              2
                   JUMP_BACKWARD           16 (to L3)
           L4:     END_FOR
                   POP_ITER
           L5:     SWAP                     2
                   STORE_FAST               2 (d)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                7 (count + NULL|self)
                   LOAD_CONST               4 ('decisions')
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
    1341           SWAP                     2
                   STORE_FAST               2 (d)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/complete")
async def api_priority_complete(item_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1343
    
    1343            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1346            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ('SELECT * FROM tasks WHERE id = ?')
                    LOAD_FAST_BORROW         0 (item_id)
                    BUILD_LIST               1
                    CALL                     2
                    STORE_FAST               1 (task)
    
    1347            LOAD_FAST_BORROW         1 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L2)
                    NOT_TAKEN
    
    1348            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1351    L2:     LOAD_GLOBAL              6 (governance)
                    LOAD_ATTR                9 (can_execute + NULL|self)
                    LOAD_CONST               5 ('tasks')
                    LOAD_CONST               6 ('complete')
                    LOAD_CONST               7 ('task_id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST               8 ('confidence')
                    LOAD_CONST               9 (1.0)
                    BUILD_MAP                2
                    CALL                     3
                    UNPACK_SEQUENCE          2
                    STORE_FAST_STORE_FAST   35 (can_exec, reason)
    
    1354            LOAD_GLOBAL             11 (create_task_bundle + NULL)
    
    1355            LOAD_CONST              10 ('Complete task: ')
                    LOAD_FAST_BORROW         1 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              11 ('title')
                    BINARY_OP               26 ([])
                    LOAD_CONST              12 (slice(None, 50, None))
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    BUILD_STRING             2
    
    1356            LOAD_CONST              13 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              14 ('status')
                    LOAD_CONST              15 ('completed')
                    BUILD_MAP                2
                    BUILD_LIST               1
    
    1357            LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              14 ('status')
                    LOAD_FAST_BORROW         1 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              14 ('status')
                    BINARY_OP               26 ([])
                    BUILD_MAP                1
                    BUILD_MAP                1
    
    1354            LOAD_CONST              16 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               4 (bundle)
    
    1360            LOAD_FAST_BORROW         2 (can_exec)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        18 (to L3)
                    NOT_TAKEN
    
    1362            LOAD_CONST              17 ('success')
                    LOAD_CONST              18 (False)
                    LOAD_CONST              19 ('requires_approval')
                    LOAD_CONST              20 (True)
                    LOAD_CONST              21 ('reason')
                    LOAD_FAST_BORROW         3 (reason)
                    LOAD_CONST              22 ('bundle_id')
                    LOAD_FAST_BORROW         4 (bundle)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
                    RETURN_VALUE
    
    1364    L3:     NOP
    
    1365    L4:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               13 (update + NULL|self)
                    LOAD_CONST               5 ('tasks')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              14 ('status')
                    LOAD_CONST              15 ('completed')
                    LOAD_CONST              23 ('updated_at')
                    LOAD_GLOBAL             14 (datetime)
                    LOAD_ATTR               16 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               19 (isoformat + NULL|self)
                    CALL                     0
                    BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    1366            LOAD_GLOBAL             21 (mark_applied + NULL)
                    LOAD_FAST_BORROW         4 (bundle)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1367            LOAD_CONST              17 ('success')
                    LOAD_CONST              20 (True)
                    LOAD_CONST              13 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              22 ('bundle_id')
                    LOAD_FAST_BORROW         4 (bundle)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                3
            L5:     RETURN_VALUE
    
      --    L6:     PUSH_EXC_INFO
    
    1368            LOAD_GLOBAL             22 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       56 (to L9)
                    NOT_TAKEN
                    STORE_FAST               5 (e)
    
    1369    L7:     LOAD_GLOBAL             25 (mark_failed + NULL)
                    LOAD_FAST                4 (bundle)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
                    LOAD_GLOBAL             27 (str + NULL)
                    LOAD_FAST                5 (e)
                    CALL                     1
                    CALL                     2
                    POP_TOP
    
    1370            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              24 (500)
                    LOAD_GLOBAL             27 (str + NULL)
                    LOAD_FAST                5 (e)
                    CALL                     1
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --    L8:     LOAD_CONST              25 (None)
                    STORE_FAST               5 (e)
                    DELETE_FAST              5 (e)
                    RERAISE                  1
    
    1368    L9:     RERAISE                  0
    
      --   L10:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L11:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L11 [0] lasti
      L4 to L5 -> L6 [0]
      L5 to L6 -> L11 [0] lasti
      L6 to L7 -> L10 [1] lasti
      L7 to L8 -> L8 [1] lasti
      L8 to L10 -> L10 [1] lasti
      L10 to L11 -> L11 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/snooze")
async def api_priority_snooze(item_id, days):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1372
    
    1372            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1375            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ('SELECT * FROM tasks WHERE id = ?')
                    LOAD_FAST_BORROW         0 (item_id)
                    BUILD_LIST               1
                    CALL                     2
                    STORE_FAST               2 (task)
    
    1376            LOAD_FAST_BORROW         2 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L2)
                    NOT_TAKEN
    
    1377            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1378    L2:     LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR                7 (get + NULL|self)
                    LOAD_CONST               5 ('due_date')
                    CALL                     1
                    STORE_FAST               3 (due)
    
    1379            LOAD_FAST_BORROW         3 (due)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L5)
            L3:     NOT_TAKEN
    
    1380    L4:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               6 (400)
                    LOAD_CONST               7 ('Cannot snooze task without due_date')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1381    L5:     LOAD_GLOBAL              8 (datetime)
                    LOAD_ATTR               10 (fromisoformat)
                    PUSH_NULL
                    LOAD_FAST_BORROW         3 (due)
                    CALL                     1
                    LOAD_GLOBAL             13 (timedelta + NULL)
                    LOAD_FAST_BORROW         1 (days)
                    LOAD_CONST               8 (('days',))
                    CALL_KW                  1
                    BINARY_OP                0 (+)
                    LOAD_ATTR               15 (date + NULL|self)
                    CALL                     0
                    LOAD_ATTR               17 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               4 (new_due)
    
    1384            LOAD_GLOBAL             18 (governance)
                    LOAD_ATTR               21 (can_execute + NULL|self)
                    LOAD_CONST               9 ('tasks')
                    LOAD_CONST              10 ('snooze')
                    LOAD_CONST              11 ('task_id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              12 ('days')
                    LOAD_FAST_BORROW         1 (days)
                    LOAD_CONST              13 ('confidence')
                    LOAD_CONST              14 (1.0)
                    BUILD_MAP                3
                    CALL                     3
                    UNPACK_SEQUENCE          2
                    STORE_FAST_STORE_FAST   86 (can_exec, reason)
    
    1387            LOAD_GLOBAL             23 (create_task_bundle + NULL)
    
    1388            LOAD_CONST              15 ('Snooze task ')
                    LOAD_FAST_BORROW         1 (days)
                    FORMAT_SIMPLE
                    LOAD_CONST              16 (' days: ')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              17 ('title')
                    BINARY_OP               26 ([])
                    LOAD_CONST              18 (slice(None, 50, None))
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    BUILD_STRING             4
    
    1389            LOAD_CONST              19 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST               5 ('due_date')
                    LOAD_FAST_BORROW         4 (new_due)
                    BUILD_MAP                2
                    BUILD_LIST               1
    
    1390            LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST               5 ('due_date')
                    LOAD_FAST_BORROW         3 (due)
                    BUILD_MAP                1
                    BUILD_MAP                1
    
    1387            LOAD_CONST              20 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               7 (bundle)
    
    1393            LOAD_FAST_BORROW         5 (can_exec)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        18 (to L6)
                    NOT_TAKEN
    
    1394            LOAD_CONST              21 ('success')
                    LOAD_CONST              22 (False)
                    LOAD_CONST              23 ('requires_approval')
                    LOAD_CONST              24 (True)
                    LOAD_CONST              25 ('reason')
                    LOAD_FAST_BORROW         6 (reason)
                    LOAD_CONST              26 ('bundle_id')
                    LOAD_FAST_BORROW         7 (bundle)
                    LOAD_CONST              19 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
                    RETURN_VALUE
    
    1396    L6:     NOP
    
    1397    L7:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               25 (update + NULL|self)
                    LOAD_CONST               9 ('tasks')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST               5 ('due_date')
                    LOAD_FAST_BORROW         4 (new_due)
                    LOAD_CONST              27 ('updated_at')
                    LOAD_GLOBAL              8 (datetime)
                    LOAD_ATTR               26 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               17 (isoformat + NULL|self)
                    CALL                     0
                    BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    1398            LOAD_GLOBAL             29 (mark_applied + NULL)
                    LOAD_FAST_BORROW         7 (bundle)
                    LOAD_CONST              19 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1399            LOAD_CONST              21 ('success')
                    LOAD_CONST              24 (True)
                    LOAD_CONST              19 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              28 ('new_due')
                    LOAD_FAST_BORROW         4 (new_due)
                    LOAD_CONST              26 ('bundle_id')
                    LOAD_FAST_BORROW         7 (bundle)
                    LOAD_CONST              19 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
            L8:     RETURN_VALUE
    
      --    L9:     PUSH_EXC_INFO
    
    1400            LOAD_GLOBAL             30 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       56 (to L12)
                    NOT_TAKEN
                    STORE_FAST               8 (e)
    
    1401   L10:     LOAD_GLOBAL             33 (mark_failed + NULL)
                    LOAD_FAST                7 (bundle)
                    LOAD_CONST              19 ('id')
                    BINARY_OP               26 ([])
                    LOAD_GLOBAL             35 (str + NULL)
                    LOAD_FAST                8 (e)
                    CALL                     1
                    CALL                     2
                    POP_TOP
    
    1402            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              29 (500)
                    LOAD_GLOBAL             35 (str + NULL)
                    LOAD_FAST                8 (e)
                    CALL                     1
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --   L11:     LOAD_CONST              30 (None)
                    STORE_FAST               8 (e)
                    DELETE_FAST              8 (e)
                    RERAISE                  1
    
    1400   L12:     RERAISE                  0
    
      --   L13:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L14:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L14 [0] lasti
      L4 to L6 -> L14 [0] lasti
      L7 to L8 -> L9 [0]
      L8 to L9 -> L14 [0] lasti
      L9 to L10 -> L13 [1] lasti
      L10 to L11 -> L11 [1] lasti
      L11 to L13 -> L13 [1] lasti
      L13 to L14 -> L14 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/delegate")
async def api_priority_delegate(item_id, to):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1404
    
    1404            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1407            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ('SELECT * FROM tasks WHERE id = ?')
                    LOAD_FAST_BORROW         0 (item_id)
                    BUILD_LIST               1
                    CALL                     2
                    STORE_FAST               2 (task)
    
    1408            LOAD_FAST_BORROW         2 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L2)
                    NOT_TAKEN
    
    1409            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1410    L2:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               5 ('SELECT id, name FROM people WHERE name = ?')
                    LOAD_FAST_BORROW         1 (to)
                    BUILD_LIST               1
                    CALL                     2
                    STORE_FAST               3 (person)
    
    1411            LOAD_FAST_BORROW         3 (person)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L5)
            L3:     NOT_TAKEN
    
    1412    L4:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               6 ('Delegate person not found')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1415    L5:     LOAD_GLOBAL              6 (governance)
                    LOAD_ATTR                9 (can_execute + NULL|self)
                    LOAD_CONST               7 ('delegation')
                    LOAD_CONST               8 ('delegate')
                    LOAD_CONST               9 ('task_id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              10 ('to')
                    LOAD_FAST_BORROW         1 (to)
                    LOAD_CONST              11 ('confidence')
                    LOAD_CONST              12 (1.0)
                    BUILD_MAP                3
                    CALL                     3
                    UNPACK_SEQUENCE          2
                    STORE_FAST_STORE_FAST   69 (can_exec, reason)
    
    1417            LOAD_GLOBAL             10 (datetime)
                    LOAD_ATTR               12 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               15 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               6 (now_iso)
    
    1419            LOAD_CONST              13 ('assignee_id')
                    LOAD_FAST_BORROW         3 (person)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
    
    1420            LOAD_CONST              15 ('assignee_name')
                    LOAD_FAST_BORROW         3 (person)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              16 ('name')
                    BINARY_OP               26 ([])
    
    1421            LOAD_CONST              17 ('delegated_by')
                    LOAD_CONST              18 ('moh')
    
    1422            LOAD_CONST              19 ('delegated_at')
                    LOAD_FAST_BORROW         6 (now_iso)
    
    1423            LOAD_CONST              20 ('updated_at')
                    LOAD_FAST_BORROW         6 (now_iso)
    
    1418            BUILD_MAP                5
                    STORE_FAST               7 (update_data)
    
    1427            LOAD_GLOBAL             17 (create_task_bundle + NULL)
    
    1428            LOAD_CONST              21 ('Delegate to ')
                    LOAD_FAST_BORROW         1 (to)
                    FORMAT_SIMPLE
                    LOAD_CONST              22 (': ')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              23 ('title')
                    BINARY_OP               26 ([])
                    LOAD_CONST              24 (slice(None, 50, None))
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    BUILD_STRING             4
    
    1429            LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    BUILD_MAP                1
                    LOAD_FAST_BORROW         7 (update_data)
                    DICT_UPDATE              1
                    BUILD_LIST               1
    
    1430            LOAD_FAST_BORROW         0 (item_id)
    
    1431            LOAD_CONST              13 ('assignee_id')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (get + NULL|self)
                    LOAD_CONST              13 ('assignee_id')
                    CALL                     1
    
    1432            LOAD_CONST              15 ('assignee_name')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (get + NULL|self)
                    LOAD_CONST              15 ('assignee_name')
                    CALL                     1
    
    1433            LOAD_CONST              17 ('delegated_by')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (get + NULL|self)
                    LOAD_CONST              17 ('delegated_by')
                    CALL                     1
    
    1434            LOAD_CONST              19 ('delegated_at')
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (get + NULL|self)
                    LOAD_CONST              19 ('delegated_at')
                    CALL                     1
    
    1430            BUILD_MAP                4
                    BUILD_MAP                1
    
    1427            LOAD_CONST              25 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST               8 (bundle)
    
    1438            LOAD_FAST_BORROW         4 (can_exec)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        18 (to L6)
                    NOT_TAKEN
    
    1439            LOAD_CONST              26 ('success')
                    LOAD_CONST              27 (False)
                    LOAD_CONST              28 ('requires_approval')
                    LOAD_CONST              29 (True)
                    LOAD_CONST              30 ('reason')
                    LOAD_FAST_BORROW         5 (reason)
                    LOAD_CONST              31 ('bundle_id')
                    LOAD_FAST_BORROW         8 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
                    RETURN_VALUE
    
    1441    L6:     NOP
    
    1442    L7:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               21 (update + NULL|self)
                    LOAD_CONST              32 ('tasks')
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 7 (item_id, update_data)
                    CALL                     3
                    POP_TOP
    
    1443            LOAD_GLOBAL             23 (mark_applied + NULL)
                    LOAD_FAST_BORROW         8 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1444            LOAD_CONST              26 ('success')
                    LOAD_CONST              29 (True)
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (item_id)
                    LOAD_CONST              33 ('delegated_to')
                    LOAD_FAST_BORROW         1 (to)
                    LOAD_CONST              31 ('bundle_id')
                    LOAD_FAST_BORROW         8 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
            L8:     RETURN_VALUE
    
      --    L9:     PUSH_EXC_INFO
    
    1445            LOAD_GLOBAL             24 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       56 (to L12)
                    NOT_TAKEN
                    STORE_FAST               9 (e)
    
    1446   L10:     LOAD_GLOBAL             27 (mark_failed + NULL)
                    LOAD_FAST                8 (bundle)
                    LOAD_CONST              14 ('id')
                    BINARY_OP               26 ([])
                    LOAD_GLOBAL             29 (str + NULL)
                    LOAD_FAST                9 (e)
                    CALL                     1
                    CALL                     2
                    POP_TOP
    
    1447            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              34 (500)
                    LOAD_GLOBAL             29 (str + NULL)
                    LOAD_FAST                9 (e)
                    CALL                     1
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --   L11:     LOAD_CONST              35 (None)
                    STORE_FAST               9 (e)
                    DELETE_FAST              9 (e)
                    RERAISE                  1
    
    1445   L12:     RERAISE                  0
    
      --   L13:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L14:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L14 [0] lasti
      L4 to L6 -> L14 [0] lasti
      L7 to L8 -> L9 [0]
      L8 to L9 -> L14 [0] lasti
      L9 to L10 -> L13 [1] lasti
      L10 to L11 -> L11 [1] lasti
      L11 to L13 -> L13 [1] lasti
      L13 to L14 -> L14 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/decisions/{decision_id}")
async def api_decision(decision_id, action):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1453
    
    1453            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1456            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ('SELECT * FROM decisions WHERE id = ?')
                    LOAD_FAST_BORROW         0 (decision_id)
                    BUILD_LIST               1
                    CALL                     2
                    STORE_FAST               2 (dec)
    
    1457            LOAD_FAST_BORROW         2 (dec)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L2)
                    NOT_TAKEN
    
    1458            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Decision not found')
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1460    L2:     LOAD_GLOBAL              6 (datetime)
                    LOAD_ATTR                8 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               11 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               3 (now_iso)
    
    1461            LOAD_FAST_BORROW         1 (action)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST               5 ('approve')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE        3 (to L3)
                    NOT_TAKEN
                    LOAD_SMALL_INT           1
                    JUMP_FORWARD             1 (to L4)
            L3:     LOAD_SMALL_INT           0
            L4:     STORE_FAST               4 (is_approved)
    
    1464            LOAD_GLOBAL             15 (create_bundle + NULL)
    
    1465            LOAD_CONST               6 ('decisions')
    
    1466            LOAD_FAST_BORROW         4 (is_approved)
                    TO_BOOL
                    POP_JUMP_IF_FALSE        3 (to L5)
                    NOT_TAKEN
                    LOAD_CONST               7 ('Approve')
                    JUMP_FORWARD             1 (to L6)
            L5:     LOAD_CONST               8 ('Reject')
            L6:     FORMAT_SIMPLE
                    LOAD_CONST               9 (' decision: ')
                    LOAD_FAST_BORROW         2 (dec)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              10 ('description')
                    LOAD_CONST              11 ('')
                    CALL                     2
                    LOAD_CONST              12 (slice(None, 50, None))
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    BUILD_STRING             3
    
    1467            LOAD_CONST              13 ('type')
                    LOAD_CONST              14 ('update')
                    LOAD_CONST              15 ('id')
                    LOAD_FAST_BORROW         0 (decision_id)
                    LOAD_CONST              16 ('target')
                    LOAD_CONST               6 ('decisions')
                    LOAD_CONST              17 ('data')
                    LOAD_CONST              18 ('approved')
                    LOAD_FAST_BORROW         4 (is_approved)
                    BUILD_MAP                1
                    BUILD_MAP                4
                    BUILD_LIST               1
    
    1468            LOAD_FAST_BORROW         0 (decision_id)
                    LOAD_CONST              18 ('approved')
                    LOAD_FAST_BORROW         2 (dec)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              18 ('approved')
                    CALL                     1
                    BUILD_MAP                1
                    BUILD_MAP                1
    
    1464            LOAD_CONST              19 (('domain', 'description', 'changes', 'pre_images'))
                    CALL_KW                  4
                    STORE_FAST               5 (bundle)
    
    1471    L7:     NOP
    
    1472    L8:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               19 (update + NULL|self)
                    LOAD_CONST               6 ('decisions')
                    LOAD_FAST_BORROW         0 (decision_id)
    
    1473            LOAD_CONST              18 ('approved')
                    LOAD_FAST_BORROW         4 (is_approved)
    
    1474            LOAD_CONST              20 ('approved_at')
                    LOAD_FAST_BORROW         3 (now_iso)
    
    1472            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    1476            LOAD_GLOBAL             21 (mark_applied + NULL)
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1477            LOAD_CONST              21 ('success')
                    LOAD_CONST              22 (True)
                    LOAD_CONST              15 ('id')
                    LOAD_FAST_BORROW         0 (decision_id)
                    LOAD_CONST              18 ('approved')
                    LOAD_FAST_BORROW         1 (action)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST              23 ('bundle_id')
                    LOAD_FAST_BORROW         5 (bundle)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    BUILD_MAP                4
            L9:     RETURN_VALUE
    
      --   L10:     PUSH_EXC_INFO
    
    1478            LOAD_GLOBAL             22 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       56 (to L13)
                    NOT_TAKEN
                    STORE_FAST               6 (e)
    
    1479   L11:     LOAD_GLOBAL             25 (mark_failed + NULL)
                    LOAD_FAST                5 (bundle)
                    LOAD_CONST              15 ('id')
                    BINARY_OP               26 ([])
                    LOAD_GLOBAL             27 (str + NULL)
                    LOAD_FAST                6 (e)
                    CALL                     1
                    CALL                     2
                    POP_TOP
    
    1480            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              24 (500)
                    LOAD_GLOBAL             27 (str + NULL)
                    LOAD_FAST                6 (e)
                    CALL                     1
                    LOAD_CONST               4 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --   L12:     LOAD_CONST              25 (None)
                    STORE_FAST               6 (e)
                    DELETE_FAST              6 (e)
                    RERAISE                  1
    
    1478   L13:     RERAISE                  0
    
      --   L14:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L15:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L7 -> L15 [0] lasti
      L8 to L9 -> L10 [0]
      L9 to L10 -> L15 [0] lasti
      L10 to L11 -> L14 [1] lasti
      L11 to L12 -> L12 [1] lasti
      L12 to L14 -> L14 [1] lasti
      L14 to L15 -> L15 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/bundles")
async def api_bundles(domain, status, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1486
    
    1486           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1489           LOAD_GLOBAL              1 (list_bundles + NULL)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (domain, status)
                   LOAD_FAST_BORROW         2 (limit)
                   LOAD_CONST               1 (('domain', 'status', 'limit'))
                   CALL_KW                  3
                   STORE_FAST               3 (bundles)
    
    1490           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         3 (bundles)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              3 (len + NULL)
                   LOAD_FAST_BORROW         3 (bundles)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/bundles/rollbackable")
async def api_bundles_rollbackable():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1492
    
    1492           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1495           LOAD_GLOBAL              1 (list_rollbackable_bundles + NULL)
                   CALL                     0
                   STORE_FAST               0 (bundles)
    
    1496           LOAD_CONST               1 ('items')
                   LOAD_FAST_BORROW         0 (bundles)
                   LOAD_CONST               2 ('total')
                   LOAD_GLOBAL              3 (len + NULL)
                   LOAD_FAST_BORROW         0 (bundles)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/bundles/summary")
async def get_bundles_summary():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1499
    
    1499           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1502           LOAD_GLOBAL              1 (list_bundles + NULL)
                   LOAD_CONST               1 (500)
                   LOAD_CONST               2 (('limit',))
                   CALL_KW                  1
                   STORE_FAST               0 (all_bundles)
    
    1504           BUILD_MAP                0
                   STORE_FAST               1 (by_status)
    
    1505           BUILD_MAP                0
                   STORE_FAST               2 (by_domain)
    
    1506           BUILD_LIST               0
                   STORE_FAST               3 (recent_applied)
    
    1508           LOAD_FAST_BORROW         0 (all_bundles)
                   GET_ITER
           L2:     FOR_ITER               183 (to L7)
                   STORE_FAST               4 (b)
    
    1509           LOAD_FAST_BORROW         4 (b)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               3 ('status')
                   LOAD_CONST               4 ('unknown')
                   CALL                     2
                   STORE_FAST               5 (status)
    
    1510           LOAD_FAST_BORROW         4 (b)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               5 ('domain')
                   LOAD_CONST               4 ('unknown')
                   CALL                     2
                   STORE_FAST               6 (domain)
    
    1512           LOAD_FAST_BORROW         1 (by_status)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_FAST_BORROW         5 (status)
                   LOAD_SMALL_INT           0
                   CALL                     2
                   LOAD_SMALL_INT           1
                   BINARY_OP                0 (+)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 21 (by_status, status)
                   STORE_SUBSCR
    
    1513           LOAD_FAST_BORROW         2 (by_domain)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_FAST_BORROW         6 (domain)
                   LOAD_SMALL_INT           0
                   CALL                     2
                   LOAD_SMALL_INT           1
                   BINARY_OP                0 (+)
                   LOAD_FAST_BORROW_LOAD_FAST_BORROW 38 (by_domain, domain)
                   STORE_SUBSCR
    
    1515           LOAD_FAST_BORROW         5 (status)
                   LOAD_CONST               6 ('applied')
                   COMPARE_OP              88 (bool(==))
           L3:     POP_JUMP_IF_TRUE         3 (to L4)
                   NOT_TAKEN
                   JUMP_BACKWARD          102 (to L2)
           L4:     LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         3 (recent_applied)
                   CALL                     1
                   LOAD_SMALL_INT          10
                   COMPARE_OP              18 (bool(<))
           L5:     POP_JUMP_IF_TRUE         3 (to L6)
                   NOT_TAKEN
                   JUMP_BACKWARD          120 (to L2)
    
    1516   L6:     LOAD_FAST_BORROW         3 (recent_applied)
                   LOAD_ATTR                7 (append + NULL|self)
    
    1517           LOAD_CONST               7 ('id')
                   LOAD_FAST_BORROW         4 (b)
                   LOAD_CONST               7 ('id')
                   BINARY_OP               26 ([])
    
    1518           LOAD_CONST               5 ('domain')
                   LOAD_FAST_BORROW         6 (domain)
    
    1519           LOAD_CONST               8 ('description')
                   LOAD_FAST_BORROW         4 (b)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               8 ('description')
                   LOAD_CONST               9 ('')
                   CALL                     2
    
    1520           LOAD_CONST              10 ('applied_at')
                   LOAD_FAST_BORROW         4 (b)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST              10 ('applied_at')
                   CALL                     1
    
    1516           BUILD_MAP                4
                   CALL                     1
                   POP_TOP
                   JUMP_BACKWARD          185 (to L2)
    
    1508   L7:     END_FOR
                   POP_ITER
    
    1523           LOAD_GLOBAL              9 (list_rollbackable_bundles + NULL)
                   CALL                     0
                   STORE_FAST               7 (rollbackable)
    
    1526           LOAD_CONST              11 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         0 (all_bundles)
                   CALL                     1
    
    1527           LOAD_CONST              12 ('by_status')
                   LOAD_FAST_BORROW         1 (by_status)
    
    1528           LOAD_CONST              13 ('by_domain')
                   LOAD_FAST_BORROW         2 (by_domain)
    
    1529           LOAD_CONST              14 ('rollbackable_count')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         7 (rollbackable)
                   CALL                     1
    
    1530           LOAD_CONST              15 ('recent_applied')
                   LOAD_FAST_BORROW         3 (recent_applied)
    
    1525           BUILD_MAP                5
                   RETURN_VALUE
    
      --   L8:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L8 [0] lasti
      L4 to L5 -> L8 [0] lasti
      L6 to L8 -> L8 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/bundles/rollback-last")
async def rollback_last_bundle(domain):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1534
    
    1534            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1537            LOAD_GLOBAL              1 (list_rollbackable_bundles + NULL)
                    CALL                     0
                    STORE_FAST               1 (rollbackable)
    
    1539            LOAD_FAST_BORROW         0 (domain)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       41 (to L8)
                    NOT_TAKEN
    
    1540            LOAD_FAST_BORROW         1 (rollbackable)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (b)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                28 (to L6)
                    STORE_FAST_LOAD_FAST    34 (b, b)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('domain')
                    CALL                     1
                    LOAD_FAST_BORROW         0 (domain)
                    COMPARE_OP              88 (bool(==))
            L4:     POP_JUMP_IF_TRUE         3 (to L5)
                    NOT_TAKEN
                    JUMP_BACKWARD           26 (to L3)
            L5:     LOAD_FAST_BORROW         2 (b)
                    LIST_APPEND              2
                    JUMP_BACKWARD           30 (to L3)
            L6:     END_FOR
                    POP_ITER
            L7:     STORE_FAST               1 (rollbackable)
                    STORE_FAST               2 (b)
    
    1542    L8:     LOAD_FAST_BORROW         1 (rollbackable)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L11)
            L9:     NOT_TAKEN
    
    1543   L10:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('No rollbackable bundles found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    1546   L11:     LOAD_GLOBAL              7 (sorted + NULL)
                    LOAD_FAST_BORROW         1 (rollbackable)
                    LOAD_CONST               4 (<code object <lambda> at 0x100987b30, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 1546>)
                    MAKE_FUNCTION
                    LOAD_CONST               5 (True)
                    LOAD_CONST               6 (('key', 'reverse'))
                    CALL_KW                  3
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    STORE_FAST               3 (most_recent)
    
    1548            LOAD_GLOBAL              9 (rollback_bundle + NULL)
                    LOAD_FAST_BORROW         3 (most_recent)
                    LOAD_CONST               7 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    STORE_FAST               4 (result)
    
    1550            LOAD_FAST_BORROW         4 (result)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               8 ('success')
                    CALL                     1
                    TO_BOOL
                    POP_JUMP_IF_FALSE       48 (to L12)
                    NOT_TAKEN
    
    1552            LOAD_CONST               8 ('success')
                    LOAD_CONST               5 (True)
    
    1553            LOAD_CONST               9 ('bundle_id')
                    LOAD_FAST_BORROW         3 (most_recent)
                    LOAD_CONST               7 ('id')
                    BINARY_OP               26 ([])
    
    1554            LOAD_CONST              10 ('description')
                    LOAD_FAST_BORROW         3 (most_recent)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              10 ('description')
                    CALL                     1
    
    1555            LOAD_CONST              11 ('rolled_back_at')
                    LOAD_FAST_BORROW         4 (result)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              11 ('rolled_back_at')
                    CALL                     1
    
    1551            BUILD_MAP                4
                    RETURN_VALUE
    
    1558   L12:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              12 (500)
                    LOAD_FAST_BORROW         4 (result)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              13 ('reason')
                    LOAD_CONST              14 ('Rollback failed')
                    CALL                     2
                    CALL                     2
                    RAISE_VARARGS            1
    
      --   L13:     SWAP                     2
                    POP_TOP
    
    1540            SWAP                     2
                    STORE_FAST               2 (b)
                    RERAISE                  0
    
      --   L14:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L14 [0] lasti
      L2 to L4 -> L13 [2]
      L5 to L7 -> L13 [2]
      L7 to L9 -> L14 [0] lasti
      L10 to L14 -> L14 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/bundles/{bundle_id}")
async def api_bundle_get(bundle_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1561
    
    1561           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1564           LOAD_GLOBAL              1 (get_bundle + NULL)
                   LOAD_FAST_BORROW         0 (bundle_id)
                   CALL                     1
                   STORE_FAST               1 (bundle)
    
    1565           LOAD_FAST_BORROW         1 (bundle)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        14 (to L2)
                   NOT_TAKEN
    
    1566           LOAD_GLOBAL              3 (HTTPException + NULL)
                   LOAD_CONST               1 (404)
                   LOAD_CONST               2 ('Bundle not found')
                   LOAD_CONST               3 (('status_code', 'detail'))
                   CALL_KW                  2
                   RAISE_VARARGS            1
    
    1567   L2:     LOAD_FAST_BORROW         1 (bundle)
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/bundles/{bundle_id}/rollback")
async def api_bundle_rollback(bundle_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1569
    
    1569            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1572            LOAD_GLOBAL              1 (get_bundle + NULL)
                    LOAD_FAST_BORROW         0 (bundle_id)
                    CALL                     1
                    STORE_FAST               1 (bundle)
    
    1573            LOAD_FAST_BORROW         1 (bundle)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        14 (to L2)
                    NOT_TAKEN
    
    1574            LOAD_GLOBAL              3 (HTTPException + NULL)
                    LOAD_CONST               1 (404)
                    LOAD_CONST               2 ('Bundle not found')
                    LOAD_CONST               3 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
    1577    L2:     LOAD_GLOBAL              4 (governance)
                    LOAD_ATTR                7 (can_execute + NULL|self)
                    LOAD_CONST               4 ('system')
                    LOAD_CONST               5 ('rollback')
                    LOAD_CONST               6 ('bundle_id')
                    LOAD_FAST_BORROW         0 (bundle_id)
                    BUILD_MAP                1
                    CALL                     3
                    UNPACK_SEQUENCE          2
                    STORE_FAST_STORE_FAST   35 (can_exec, reason)
    
    1578            LOAD_FAST_BORROW         2 (can_exec)
                    TO_BOOL
                    POP_JUMP_IF_TRUE         9 (to L3)
                    NOT_TAKEN
    
    1579            LOAD_CONST               7 ('success')
                    LOAD_CONST               8 (False)
                    LOAD_CONST               9 ('requires_approval')
                    LOAD_CONST              10 (True)
                    LOAD_CONST              11 ('reason')
                    LOAD_FAST_BORROW         3 (reason)
                    BUILD_MAP                3
                    RETURN_VALUE
    
    1581    L3:     NOP
    
    1582    L4:     LOAD_GLOBAL              9 (rollback_bundle + NULL)
                    LOAD_FAST_BORROW         0 (bundle_id)
                    CALL                     1
                    STORE_FAST               4 (result)
    
    1583            LOAD_CONST               7 ('success')
                    LOAD_CONST              10 (True)
                    LOAD_CONST              12 ('bundle')
                    LOAD_FAST_BORROW         4 (result)
                    BUILD_MAP                2
            L5:     RETURN_VALUE
    
      --    L6:     PUSH_EXC_INFO
    
    1584            LOAD_GLOBAL             10 (ValueError)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       28 (to L9)
                    NOT_TAKEN
                    STORE_FAST               5 (e)
    
    1585    L7:     LOAD_GLOBAL              3 (HTTPException + NULL)
                    LOAD_CONST              13 (400)
                    LOAD_GLOBAL             13 (str + NULL)
                    LOAD_FAST                5 (e)
                    CALL                     1
                    LOAD_CONST               3 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --    L8:     LOAD_CONST              14 (None)
                    STORE_FAST               5 (e)
                    DELETE_FAST              5 (e)
                    RERAISE                  1
    
    1586    L9:     LOAD_GLOBAL             14 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       28 (to L14)
           L10:     NOT_TAKEN
           L11:     STORE_FAST               5 (e)
    
    1587   L12:     LOAD_GLOBAL              3 (HTTPException + NULL)
                    LOAD_CONST              15 (500)
                    LOAD_GLOBAL             13 (str + NULL)
                    LOAD_FAST                5 (e)
                    CALL                     1
                    LOAD_CONST               3 (('status_code', 'detail'))
                    CALL_KW                  2
                    RAISE_VARARGS            1
    
      --   L13:     LOAD_CONST              14 (None)
                    STORE_FAST               5 (e)
                    DELETE_FAST              5 (e)
                    RERAISE                  1
    
    1586   L14:     RERAISE                  0
    
      --   L15:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L16:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L16 [0] lasti
      L4 to L5 -> L6 [0]
      L5 to L6 -> L16 [0] lasti
      L6 to L7 -> L15 [1] lasti
      L7 to L8 -> L8 [1] lasti
      L8 to L10 -> L15 [1] lasti
      L11 to L12 -> L15 [1] lasti
      L12 to L13 -> L13 [1] lasti
      L13 to L15 -> L15 [1] lasti
      L15 to L16 -> L16 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/calibration")
async def api_calibration_last():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1595
    
    1595           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1598           LOAD_GLOBAL              0 (calibration_engine)
                   LOAD_ATTR                3 (get_last_calibration + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (report)
    
    1599           LOAD_FAST_BORROW         0 (report)
                   TO_BOOL
                   POP_JUMP_IF_TRUE         5 (to L2)
                   NOT_TAKEN
    
    1600           LOAD_CONST               1 ('message')
                   LOAD_CONST               2 ('No calibration reports yet')
                   BUILD_MAP                1
                   RETURN_VALUE
    
    1601   L2:     LOAD_FAST_BORROW         0 (report)
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/calibration/run")
async def api_calibration_run():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1603
    
    1603           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1606           LOAD_GLOBAL              0 (calibration_engine)
                   LOAD_ATTR                3 (run_weekly_calibration + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (report)
    
    1607           LOAD_CONST               1 ('success')
                   LOAD_CONST               2 (True)
                   LOAD_CONST               3 ('report')
                   LOAD_FAST_BORROW         0 (report)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/feedback")
async def api_feedback(feedback):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1619
    
    1619           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1622           LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR                2 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                5 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               1 (now_iso)
    
    1625           LOAD_GLOBAL              6 (store)
                   LOAD_ATTR                9 (insert + NULL|self)
                   LOAD_CONST               1 ('feedback')
    
    1626           LOAD_CONST               2 ('id')
                   LOAD_CONST               3 ('feedback_')
                   LOAD_FAST_BORROW         1 (now_iso)
                   LOAD_ATTR               11 (replace + NULL|self)
                   LOAD_CONST               4 (':')
                   LOAD_CONST               5 ('-')
                   CALL                     2
                   FORMAT_SIMPLE
                   BUILD_STRING             2
    
    1627           LOAD_CONST               6 ('feedback_type')
                   LOAD_FAST_BORROW         0 (feedback)
                   LOAD_ATTR               12 (type)
    
    1628           LOAD_CONST               7 ('details')
                   LOAD_GLOBAL             14 (json)
                   LOAD_ATTR               16 (dumps)
                   PUSH_NULL
                   LOAD_CONST               8 ('context')
                   LOAD_FAST_BORROW         0 (feedback)
                   LOAD_ATTR               18 (context)
                   LOAD_CONST               9 ('notes')
                   LOAD_FAST_BORROW         0 (feedback)
                   LOAD_ATTR               20 (notes)
                   BUILD_MAP                2
                   CALL                     1
    
    1629           LOAD_CONST              10 ('created_at')
                   LOAD_FAST_BORROW         1 (now_iso)
    
    1625           BUILD_MAP                4
                   CALL                     2
                   POP_TOP
    
    1632           LOAD_CONST              11 ('success')
                   LOAD_CONST              12 (True)
                   LOAD_CONST              13 ('message')
                   LOAD_CONST              14 ('Feedback recorded')
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/priorities")
async def get_priorities(limit, type):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1639
    
    1639            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1642            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get_cache + NULL|self)
                    LOAD_CONST               1 ('priority_queue')
                    CALL                     1
                    STORE_FAST               2 (queue)
    
    1644            LOAD_FAST_BORROW         2 (queue)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        31 (to L2)
                    NOT_TAKEN
    
    1645            LOAD_GLOBAL              4 (analyzers)
                    LOAD_ATTR                6 (priority)
                    LOAD_ATTR                9 (analyze + NULL|self)
                    CALL                     0
                    STORE_FAST               2 (queue)
    
    1647    L2:     LOAD_FAST_BORROW         1 (type)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       33 (to L11)
            L3:     NOT_TAKEN
    
    1648    L4:     LOAD_FAST_BORROW         2 (queue)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      3 (item)
                    SWAP                     2
            L5:     BUILD_LIST               0
                    SWAP                     2
            L6:     FOR_ITER                20 (to L9)
                    STORE_FAST_LOAD_FAST    51 (item, item)
                    LOAD_CONST               2 ('type')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW         1 (type)
                    COMPARE_OP              88 (bool(==))
            L7:     POP_JUMP_IF_TRUE         3 (to L8)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L6)
            L8:     LOAD_FAST_BORROW         3 (item)
                    LIST_APPEND              2
                    JUMP_BACKWARD           22 (to L6)
            L9:     END_FOR
                    POP_ITER
           L10:     STORE_FAST               2 (queue)
                    STORE_FAST               3 (item)
    
    1651   L11:     LOAD_CONST               3 ('items')
                    LOAD_FAST_BORROW         2 (queue)
                    LOAD_CONST               4 (None)
                    LOAD_FAST_BORROW         0 (limit)
                    BINARY_SLICE
    
    1652            LOAD_CONST               5 ('total')
                    LOAD_GLOBAL             11 (len + NULL)
                    LOAD_FAST_BORROW         2 (queue)
                    CALL                     1
    
    1650            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L12:     SWAP                     2
                    POP_TOP
    
    1648            SWAP                     2
                    STORE_FAST               3 (item)
                    RERAISE                  0
    
      --   L13:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L13 [0] lasti
      L4 to L5 -> L13 [0] lasti
      L5 to L7 -> L12 [2]
      L8 to L10 -> L12 [2]
      L10 to L13 -> L13 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/complete")
async def complete_item(item_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1656
    
    1656           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1660           LOAD_FAST_BORROW         0 (item_id)
                   LOAD_ATTR                1 (startswith + NULL|self)
                   LOAD_CONST               1 ('asana_')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE       62 (to L2)
                   NOT_TAKEN
    
    1661           LOAD_GLOBAL              2 (store)
                   LOAD_ATTR                5 (update + NULL|self)
                   LOAD_CONST               2 ('tasks')
                   LOAD_FAST_BORROW         0 (item_id)
                   LOAD_CONST               3 ('status')
                   LOAD_CONST               4 ('done')
                   LOAD_CONST               5 ('updated_at')
                   LOAD_GLOBAL              6 (datetime)
                   LOAD_ATTR                8 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               11 (isoformat + NULL|self)
                   CALL                     0
                   BUILD_MAP                2
                   CALL                     3
                   POP_TOP
                   JUMP_FORWARD            61 (to L6)
    
    1662   L2:     LOAD_FAST_BORROW         0 (item_id)
                   LOAD_ATTR                1 (startswith + NULL|self)
                   LOAD_CONST               6 ('gmail_')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE       27 (to L5)
           L3:     NOT_TAKEN
    
    1663   L4:     LOAD_GLOBAL              2 (store)
                   LOAD_ATTR                5 (update + NULL|self)
                   LOAD_CONST               7 ('communications')
                   LOAD_FAST_BORROW         0 (item_id)
                   LOAD_CONST               8 ('processed')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                1
                   CALL                     3
                   POP_TOP
                   JUMP_FORWARD            12 (to L6)
    
    1665   L5:     LOAD_GLOBAL             13 (HTTPException + NULL)
                   LOAD_CONST               9 (404)
                   LOAD_CONST              10 ('Item not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
    1668   L6:     LOAD_GLOBAL              2 (store)
                   LOAD_ATTR               15 (clear_cache + NULL|self)
                   LOAD_CONST              11 ('priority_queue')
                   CALL                     1
                   POP_TOP
    
    1670           LOAD_CONST               3 ('status')
                   LOAD_CONST              12 ('completed')
                   LOAD_CONST              13 ('id')
                   LOAD_FAST_BORROW         0 (item_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L7 [0] lasti
      L4 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/snooze")
async def snooze_item(item_id, hours):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1673
    
    1673           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1678           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               1 ('tasks')
                   LOAD_FAST_BORROW         0 (item_id)
                   CALL                     2
                   COPY                     1
                   TO_BOOL
                   POP_JUMP_IF_TRUE        23 (to L2)
                   NOT_TAKEN
                   POP_TOP
                   LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               2 ('communications')
                   LOAD_FAST_BORROW         0 (item_id)
                   CALL                     2
           L2:     STORE_FAST               2 (item)
    
    1679           LOAD_FAST_BORROW         2 (item)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L5)
           L3:     NOT_TAKEN
    
    1680   L4:     LOAD_GLOBAL              5 (HTTPException + NULL)
                   LOAD_CONST               3 (404)
                   LOAD_CONST               4 ('Item not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
    1682   L5:     LOAD_CONST               5 ('status')
                   LOAD_CONST               6 ('snoozed')
                   LOAD_CONST               7 ('id')
                   LOAD_FAST_BORROW         0 (item_id)
                   LOAD_CONST               8 ('until_hours')
                   LOAD_FAST_BORROW         1 (hours)
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L6:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L6 [0] lasti
      L4 to L6 -> L6 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/{item_id}/delegate")
async def delegate_item(item_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1690
    
    1690           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1693           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('DelegationHandler',))
                   IMPORT_NAME              0 (lib.executor.handlers)
                   IMPORT_FROM              1 (DelegationHandler)
                   STORE_FAST               2 (DelegationHandler)
                   POP_TOP
    
    1695           LOAD_FAST_BORROW         2 (DelegationHandler)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   STORE_FAST               3 (handler)
    
    1696           LOAD_FAST_BORROW         3 (handler)
                   LOAD_ATTR                7 (execute + NULL|self)
    
    1697           LOAD_CONST               2 ('action_type')
                   LOAD_CONST               3 ('delegate')
    
    1698           LOAD_CONST               4 ('task_id')
                   LOAD_FAST_BORROW         0 (item_id)
    
    1699           LOAD_CONST               5 ('data')
    
    1700           LOAD_CONST               6 ('delegate_to')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR                8 (delegate_to)
    
    1701           LOAD_CONST               7 ('message')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               10 (message)
    
    1699           BUILD_MAP                2
    
    1696           BUILD_MAP                3
                   CALL                     1
                   STORE_FAST               4 (result)
    
    1705           LOAD_FAST_BORROW         4 (result)
                   LOAD_CONST               8 ('success')
                   BINARY_OP               26 ([])
                   TO_BOOL
                   POP_JUMP_IF_TRUE        29 (to L2)
                   NOT_TAKEN
    
    1706           LOAD_GLOBAL             13 (HTTPException + NULL)
                   LOAD_CONST               9 (400)
                   LOAD_FAST_BORROW         4 (result)
                   LOAD_ATTR               15 (get + NULL|self)
                   LOAD_CONST              10 ('error')
                   LOAD_CONST              11 ('Delegation failed')
                   CALL                     2
                   CALL                     2
                   RAISE_VARARGS            1
    
    1708   L2:     LOAD_GLOBAL              4 (store)
                   LOAD_ATTR               17 (clear_cache + NULL|self)
                   LOAD_CONST              12 ('priority_queue')
                   CALL                     1
                   POP_TOP
    
    1709           LOAD_FAST_BORROW         4 (result)
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/priorities/filtered")
async def get_priorities_filtered(due, assignee, source, project, q, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1712
    
      --            MAKE_CELL               15 (date)
    
    1712            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1722            LOAD_SMALL_INT           0
                    LOAD_CONST               1 (('date', 'timedelta'))
                    IMPORT_NAME              0 (datetime)
                    IMPORT_FROM              1 (date)
                    STORE_DEREF             15 (date)
                    IMPORT_FROM              2 (timedelta)
                    STORE_FAST               6 (timedelta)
                    POP_TOP
    
    1724            LOAD_CONST               2 ("status = 'pending'")
                    BUILD_LIST               1
                    STORE_FAST               7 (conditions)
    
    1725            BUILD_LIST               0
                    STORE_FAST               8 (params)
    
    1726            LOAD_DEREF              15 (date)
                    LOAD_ATTR                7 (today + NULL|self)
                    CALL                     0
                    LOAD_ATTR                9 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               9 (today)
    
    1727            LOAD_DEREF              15 (date)
                    LOAD_ATTR                7 (today + NULL|self)
                    CALL                     0
                    LOAD_FAST_BORROW         6 (timedelta)
                    PUSH_NULL
                    LOAD_SMALL_INT           7
                    LOAD_CONST               3 (('days',))
                    CALL_KW                  1
                    BINARY_OP                0 (+)
                    LOAD_ATTR                9 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST              10 (week_end)
    
    1729            LOAD_FAST_BORROW         0 (due)
                    LOAD_CONST               4 ('today')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       36 (to L2)
                    NOT_TAKEN
    
    1730            LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST               5 ('due_date = ?')
                    CALL                     1
                    POP_TOP
    
    1731            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_FAST_BORROW         9 (today)
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD            84 (to L4)
    
    1732    L2:     LOAD_FAST_BORROW         0 (due)
                    LOAD_CONST               6 ('week')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       37 (to L3)
                    NOT_TAKEN
    
    1733            LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST               7 ('due_date BETWEEN ? AND ?')
                    CALL                     1
                    POP_TOP
    
    1734            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               13 (extend + NULL|self)
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 154 (today, week_end)
                    BUILD_LIST               2
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD            41 (to L4)
    
    1735    L3:     LOAD_FAST_BORROW         0 (due)
                    LOAD_CONST               8 ('overdue')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       35 (to L4)
                    NOT_TAKEN
    
    1736            LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST               9 ('due_date < ?')
                    CALL                     1
                    POP_TOP
    
    1737            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_FAST_BORROW         9 (today)
                    CALL                     1
                    POP_TOP
    
    1739    L4:     LOAD_FAST_BORROW         1 (assignee)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L7)
            L5:     NOT_TAKEN
    
    1740    L6:     LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              10 ('assignee LIKE ?')
                    CALL                     1
                    POP_TOP
    
    1741            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              11 ('%')
                    LOAD_FAST_BORROW         1 (assignee)
                    FORMAT_SIMPLE
                    LOAD_CONST              11 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
    1743    L7:     LOAD_FAST_BORROW         2 (source)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L10)
            L8:     NOT_TAKEN
    
    1744    L9:     LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              12 ('source LIKE ?')
                    CALL                     1
                    POP_TOP
    
    1745            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              11 ('%')
                    LOAD_FAST_BORROW         2 (source)
                    FORMAT_SIMPLE
                    LOAD_CONST              11 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
    1747   L10:     LOAD_FAST_BORROW         3 (project)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L13)
           L11:     NOT_TAKEN
    
    1748   L12:     LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              13 ('project LIKE ?')
                    CALL                     1
                    POP_TOP
    
    1749            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              11 ('%')
                    LOAD_FAST_BORROW         3 (project)
                    FORMAT_SIMPLE
                    LOAD_CONST              11 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
    1751   L13:     LOAD_FAST_BORROW         4 (q)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       39 (to L16)
           L14:     NOT_TAKEN
    
    1752   L15:     LOAD_FAST_BORROW         7 (conditions)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              14 ('title LIKE ?')
                    CALL                     1
                    POP_TOP
    
    1753            LOAD_FAST_BORROW         8 (params)
                    LOAD_ATTR               11 (append + NULL|self)
                    LOAD_CONST              11 ('%')
                    LOAD_FAST_BORROW         4 (q)
                    FORMAT_SIMPLE
                    LOAD_CONST              11 ('%')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
    1755   L16:     LOAD_CONST              15 (' AND ')
                    LOAD_ATTR               15 (join + NULL|self)
                    LOAD_FAST_BORROW         7 (conditions)
                    CALL                     1
                    STORE_FAST              11 (where)
    
    1756            LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               19 (query + NULL|self)
    
    1757            LOAD_CONST              16 ('SELECT * FROM tasks WHERE ')
                    LOAD_FAST_BORROW        11 (where)
                    FORMAT_SIMPLE
                    LOAD_CONST              17 (' ORDER BY priority DESC, due_date ASC LIMIT ?')
                    BUILD_STRING             3
    
    1758            LOAD_FAST_BORROW_LOAD_FAST_BORROW 133 (params, limit)
                    BUILD_LIST               1
                    BINARY_OP                0 (+)
    
    1756            CALL                     2
                    STORE_FAST              12 (tasks)
    
    1762            LOAD_FAST_BORROW        15 (date)
                    BUILD_TUPLE              1
                    LOAD_CONST              18 (<code object get_reasons at 0x148f96b60, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 1762>)
                    MAKE_FUNCTION
                    SET_FUNCTION_ATTRIBUTE   8 (closure)
                    STORE_FAST              13 (get_reasons)
    
    1782            LOAD_CONST              19 ('items')
    
    1791            LOAD_FAST_BORROW        12 (tasks)
                    GET_ITER
    
    1782            LOAD_FAST_AND_CLEAR     14 (t)
                    SWAP                     2
           L17:     BUILD_LIST               0
                    SWAP                     2
    
    1791   L18:     FOR_ITER                76 (to L19)
                    STORE_FAST              14 (t)
    
    1783            LOAD_CONST              20 ('id')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              20 ('id')
                    BINARY_OP               26 ([])
    
    1784            LOAD_CONST              21 ('title')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              21 ('title')
                    BINARY_OP               26 ([])
    
    1785            LOAD_CONST              22 ('score')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              23 ('priority')
                    BINARY_OP               26 ([])
    
    1786            LOAD_CONST              24 ('due')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              25 ('due_date')
                    BINARY_OP               26 ([])
    
    1787            LOAD_CONST              26 ('assignee')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              26 ('assignee')
                    BINARY_OP               26 ([])
    
    1788            LOAD_CONST              27 ('source')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              27 ('source')
                    BINARY_OP               26 ([])
    
    1789            LOAD_CONST              28 ('project')
                    LOAD_FAST_BORROW        14 (t)
                    LOAD_CONST              28 ('project')
                    BINARY_OP               26 ([])
    
    1790            LOAD_CONST              29 ('reasons')
                    LOAD_FAST_BORROW        13 (get_reasons)
                    PUSH_NULL
                    LOAD_FAST_BORROW        14 (t)
                    CALL                     1
    
    1782            BUILD_MAP                8
                    LIST_APPEND              2
                    JUMP_BACKWARD           78 (to L18)
    
    1791   L19:     END_FOR
                    POP_ITER
    
    1782   L20:     SWAP                     2
                    STORE_FAST              14 (t)
    
    1792            LOAD_CONST              30 ('total')
                    LOAD_GLOBAL             16 (store)
                    LOAD_ATTR               21 (count + NULL|self)
                    LOAD_CONST              31 ('tasks')
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 184 (where, params)
                    CALL                     3
    
    1781            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L21:     SWAP                     2
                    POP_TOP
    
    1782            SWAP                     2
                    STORE_FAST              14 (t)
                    RERAISE                  0
    
      --   L22:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L5 -> L22 [0] lasti
      L6 to L8 -> L22 [0] lasti
      L9 to L11 -> L22 [0] lasti
      L12 to L14 -> L22 [0] lasti
      L15 to L17 -> L22 [0] lasti
      L17 to L20 -> L21 [3]
      L20 to L22 -> L22 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/priorities/bulk")
async def bulk_action(body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1810
    
    1810            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    1822            LOAD_SMALL_INT           0
                    LOAD_CONST               1 (('create_task_bundle', 'mark_applied'))
                    IMPORT_NAME              0 (lib.change_bundles)
                    IMPORT_FROM              1 (create_task_bundle)
                    STORE_FAST               1 (create_task_bundle)
                    IMPORT_FROM              2 (mark_applied)
                    STORE_FAST               2 (mark_applied)
                    POP_TOP
    
    1824            LOAD_CONST              43 (('archive', 'complete', 'delete', 'assign', 'snooze', 'priority', 'project'))
                    STORE_FAST               3 (valid_actions)
    
    1825            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_FAST_BORROW         3 (valid_actions)
                    CONTAINS_OP              1 (not in)
                    POP_JUMP_IF_FALSE       31 (to L2)
                    NOT_TAKEN
    
    1826            LOAD_GLOBAL              9 (HTTPException + NULL)
                    LOAD_CONST               9 (400)
                    LOAD_CONST              10 ('Action must be one of: ')
                    LOAD_CONST              11 (', ')
                    LOAD_ATTR               11 (join + NULL|self)
                    LOAD_FAST_BORROW         3 (valid_actions)
                    CALL                     1
                    FORMAT_SIMPLE
                    BUILD_STRING             2
                    CALL                     2
                    RAISE_VARARGS            1
    
    1828    L2:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               12 (ids)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L5)
            L3:     NOT_TAKEN
    
    1829    L4:     LOAD_GLOBAL              9 (HTTPException + NULL)
                    LOAD_CONST               9 (400)
                    LOAD_CONST              12 ('No task IDs provided')
                    CALL                     2
                    RAISE_VARARGS            1
    
    1832    L5:     BUILD_MAP                0
                    STORE_FAST               4 (pre_images)
    
    1833            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               12 (ids)
                    GET_ITER
            L6:     FOR_ITER               124 (to L9)
                    STORE_FAST               5 (task_id)
    
    1834            LOAD_GLOBAL             14 (store)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              13 ('tasks')
                    LOAD_FAST_BORROW         5 (task_id)
                    CALL                     2
                    STORE_FAST               6 (task)
    
    1835            LOAD_FAST_BORROW         6 (task)
                    TO_BOOL
            L7:     POP_JUMP_IF_TRUE         3 (to L8)
                    NOT_TAKEN
                    JUMP_BACKWARD           35 (to L6)
    
    1837    L8:     LOAD_CONST              14 ('status')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              14 ('status')
                    CALL                     1
    
    1838            LOAD_CONST              15 ('assignee')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              15 ('assignee')
                    CALL                     1
    
    1839            LOAD_CONST              16 ('due_date')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST              16 ('due_date')
                    CALL                     1
    
    1840            LOAD_CONST               7 ('priority')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST               7 ('priority')
                    CALL                     1
    
    1841            LOAD_CONST               8 ('project')
                    LOAD_FAST_BORROW         6 (task)
                    LOAD_ATTR               17 (get + NULL|self)
                    LOAD_CONST               8 ('project')
                    CALL                     1
    
    1836            BUILD_MAP                5
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 69 (pre_images, task_id)
                    STORE_SUBSCR
                    JUMP_BACKWARD          126 (to L6)
    
    1833    L9:     END_FOR
                    POP_ITER
    
    1845            BUILD_LIST               0
                    STORE_FAST               7 (updates)
    
    1846            LOAD_GLOBAL             18 (datetime)
                    LOAD_ATTR               20 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               23 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               8 (now)
    
    1848            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               12 (ids)
                    GET_ITER
           L10:     EXTENDED_ARG             1
                    FOR_ITER               450 (to L28)
                    STORE_FAST               5 (task_id)
    
    1849            LOAD_FAST_BORROW_LOAD_FAST_BORROW 84 (task_id, pre_images)
                    CONTAINS_OP              1 (not in)
                    POP_JUMP_IF_FALSE        3 (to L11)
                    NOT_TAKEN
    
    1850            JUMP_BACKWARD           12 (to L10)
    
    1852   L11:     LOAD_CONST              17 ('updated_at')
                    LOAD_FAST_BORROW         8 (now)
                    BUILD_MAP                1
                    STORE_FAST               9 (update_data)
    
    1854            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               2 ('archive')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE        8 (to L12)
                    NOT_TAKEN
    
    1855            LOAD_CONST              18 ('archived')
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              14 ('status')
                    STORE_SUBSCR
                    EXTENDED_ARG             1
                    JUMP_FORWARD           377 (to L27)
    
    1856   L12:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               3 ('complete')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE        8 (to L13)
                    NOT_TAKEN
    
    1857            LOAD_CONST              19 ('completed')
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              14 ('status')
                    STORE_SUBSCR
                    EXTENDED_ARG             1
                    JUMP_FORWARD           353 (to L27)
    
    1858   L13:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               4 ('delete')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE        8 (to L14)
                    NOT_TAKEN
    
    1859            LOAD_CONST              20 ('deleted')
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              14 ('status')
                    STORE_SUBSCR
                    EXTENDED_ARG             1
                    JUMP_FORWARD           329 (to L27)
    
    1860   L14:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               5 ('assign')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       44 (to L16)
                    NOT_TAKEN
    
    1861            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               24 (assignee)
                    POP_JUMP_IF_NOT_NONE    13 (to L15)
                    NOT_TAKEN
    
    1862            LOAD_GLOBAL              9 (HTTPException + NULL)
                    LOAD_CONST               9 (400)
                    LOAD_CONST              22 ('assignee field required for assign action')
                    CALL                     2
                    RAISE_VARARGS            1
    
    1863   L15:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               24 (assignee)
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              15 ('assignee')
                    STORE_SUBSCR
                    EXTENDED_ARG             1
                    JUMP_FORWARD           269 (to L27)
    
    1864   L16:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               6 ('snooze')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE      142 (to L24)
                    NOT_TAKEN
    
    1865            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               26 (snooze_until)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       17 (to L19)
           L17:     NOT_TAKEN
    
    1866   L18:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               26 (snooze_until)
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              16 ('due_date')
                    STORE_SUBSCR
                    JUMP_FORWARD           101 (to L23)
    
    1867   L19:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               28 (snooze_days)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       72 (to L22)
           L20:     NOT_TAKEN
    
    1868   L21:     LOAD_SMALL_INT           0
                    LOAD_CONST              23 (('timedelta',))
                    IMPORT_NAME              9 (datetime)
                    IMPORT_FROM             15 (timedelta)
                    STORE_FAST              10 (timedelta)
                    POP_TOP
    
    1869            LOAD_GLOBAL             18 (datetime)
                    LOAD_ATTR               20 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_FAST_BORROW        10 (timedelta)
                    PUSH_NULL
                    LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               28 (snooze_days)
                    LOAD_CONST              24 (('days',))
                    CALL_KW                  1
                    BINARY_OP                0 (+)
                    LOAD_ATTR               33 (strftime + NULL|self)
                    LOAD_CONST              25 ('%Y-%m-%d')
                    CALL                     1
                    STORE_FAST              11 (new_date)
    
    1870            LOAD_FAST_BORROW_LOAD_FAST_BORROW 185 (new_date, update_data)
                    LOAD_CONST              16 ('due_date')
                    STORE_SUBSCR
                    JUMP_FORWARD            12 (to L23)
    
    1872   L22:     LOAD_GLOBAL              9 (HTTPException + NULL)
                    LOAD_CONST               9 (400)
                    LOAD_CONST              26 ('snooze_days or snooze_until required for snooze action')
                    CALL                     2
                    RAISE_VARARGS            1
    
    1873   L23:     LOAD_CONST              27 ('snoozed')
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST              14 ('status')
                    STORE_SUBSCR
                    JUMP_FORWARD           111 (to L27)
    
    1874   L24:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               7 ('priority')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       63 (to L26)
                    NOT_TAKEN
    
    1875            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               34 (priority)
                    POP_JUMP_IF_NOT_NONE    13 (to L25)
                    NOT_TAKEN
    
    1876            LOAD_GLOBAL              9 (HTTPException + NULL)
                    LOAD_CONST               9 (400)
                    LOAD_CONST              28 ('priority field required for priority action')
                    CALL                     2
                    RAISE_VARARGS            1
    
    1877   L25:     LOAD_GLOBAL             37 (max + NULL)
                    LOAD_SMALL_INT          10
                    LOAD_GLOBAL             39 (min + NULL)
                    LOAD_SMALL_INT          90
                    LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               34 (priority)
                    CALL                     2
                    CALL                     2
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST               7 ('priority')
                    STORE_SUBSCR
                    JUMP_FORWARD            32 (to L27)
    
    1878   L26:     LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               8 ('project')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       16 (to L27)
                    NOT_TAKEN
    
    1879            LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR               40 (project)
                    LOAD_FAST_BORROW         9 (update_data)
                    LOAD_CONST               8 ('project')
                    STORE_SUBSCR
    
    1881   L27:     LOAD_FAST_BORROW         7 (updates)
                    LOAD_ATTR               43 (append + NULL|self)
                    LOAD_CONST              29 ('id')
                    LOAD_FAST_BORROW         5 (task_id)
                    LOAD_CONST              30 ('type')
                    LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST              31 ('data')
                    LOAD_FAST_BORROW         9 (update_data)
                    BUILD_MAP                3
                    CALL                     1
                    POP_TOP
                    EXTENDED_ARG             1
                    JUMP_BACKWARD          453 (to L10)
    
    1848   L28:     END_FOR
                    POP_ITER
    
    1884            LOAD_FAST_BORROW         1 (create_task_bundle)
                    PUSH_NULL
    
    1885            LOAD_CONST              32 ('Bulk ')
                    LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
                    FORMAT_SIMPLE
                    LOAD_CONST              33 (': ')
                    LOAD_GLOBAL             45 (len + NULL)
                    LOAD_FAST_BORROW         7 (updates)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST              34 (' tasks')
                    BUILD_STRING             5
    
    1886            LOAD_FAST_BORROW         7 (updates)
    
    1887            LOAD_FAST_BORROW         4 (pre_images)
    
    1884            LOAD_CONST              35 (('description', 'updates', 'pre_images'))
                    CALL_KW                  3
                    STORE_FAST              12 (bundle)
    
    1891            LOAD_SMALL_INT           0
                    STORE_FAST              13 (updated)
    
    1892            LOAD_FAST_BORROW         7 (updates)
                    GET_ITER
           L29:     FOR_ITER                50 (to L33)
                    STORE_FAST              14 (update)
    
    1893   L30:     NOP
    
    1894   L31:     LOAD_GLOBAL             14 (store)
                    LOAD_ATTR               47 (update + NULL|self)
                    LOAD_CONST              13 ('tasks')
                    LOAD_FAST_BORROW        14 (update)
                    LOAD_CONST              29 ('id')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW        14 (update)
                    LOAD_CONST              31 ('data')
                    BINARY_OP               26 ([])
                    CALL                     3
                    POP_TOP
    
    1895            LOAD_FAST_BORROW        13 (updated)
                    LOAD_SMALL_INT           1
                    BINARY_OP               13 (+=)
                    STORE_FAST              13 (updated)
           L32:     JUMP_BACKWARD           52 (to L29)
    
    1892   L33:     END_FOR
                    POP_ITER
    
    1899            LOAD_FAST_BORROW         2 (mark_applied)
                    PUSH_NULL
                    LOAD_FAST_BORROW        12 (bundle)
                    LOAD_CONST              29 ('id')
                    BINARY_OP               26 ([])
                    CALL                     1
                    POP_TOP
    
    1900            LOAD_GLOBAL             14 (store)
                    LOAD_ATTR               53 (clear_cache + NULL|self)
                    LOAD_CONST              37 ('priority_queue')
                    CALL                     1
                    POP_TOP
    
    1903            LOAD_CONST              38 ('success')
                    LOAD_CONST              39 (True)
    
    1904            LOAD_CONST              40 ('updated')
                    LOAD_FAST_BORROW        13 (updated)
    
    1905            LOAD_CONST              41 ('action')
                    LOAD_FAST_BORROW         0 (body)
                    LOAD_ATTR                6 (action)
    
    1906            LOAD_CONST              42 ('bundle_id')
                    LOAD_FAST_BORROW        12 (bundle)
                    LOAD_CONST              29 ('id')
                    BINARY_OP               26 ([])
    
    1902            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L34:     PUSH_EXC_INFO
    
    1896            LOAD_GLOBAL             48 (Exception)
                    CHECK_EXC_MATCH
                    POP_JUMP_IF_FALSE       36 (to L38)
                    NOT_TAKEN
                    STORE_FAST              15 (e)
    
    1897   L35:     LOAD_GLOBAL             51 (print + NULL)
                    LOAD_CONST              36 ('Failed to update ')
                    LOAD_FAST               14 (update)
                    LOAD_CONST              29 ('id')
                    BINARY_OP               26 ([])
                    FORMAT_SIMPLE
                    LOAD_CONST              33 (': ')
                    LOAD_FAST               15 (e)
                    FORMAT_SIMPLE
                    BUILD_STRING             4
                    CALL                     1
                    POP_TOP
           L36:     POP_EXCEPT
                    LOAD_CONST              21 (None)
                    STORE_FAST              15 (e)
                    DELETE_FAST             15 (e)
                    JUMP_BACKWARD          158 (to L29)
    
      --   L37:     LOAD_CONST              21 (None)
                    STORE_FAST              15 (e)
                    DELETE_FAST             15 (e)
                    RERAISE                  1
    
    1896   L38:     RERAISE                  0
    
      --   L39:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L40:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L40 [0] lasti
      L4 to L7 -> L40 [0] lasti
      L8 to L17 -> L40 [0] lasti
      L18 to L20 -> L40 [0] lasti
      L21 to L30 -> L40 [0] lasti
      L31 to L32 -> L34 [1]
      L32 to L34 -> L40 [0] lasti
      L34 to L35 -> L39 [2] lasti
      L35 to L36 -> L37 [2] lasti
      L36 to L37 -> L40 [0] lasti
      L37 to L39 -> L39 [2] lasti
      L39 to L40 -> L40 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/filters")
async def get_saved_filters():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1920
    
    1920           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    1925           LOAD_CONST               1 ('id')
                   LOAD_CONST               2 ('today')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST               4 ('📅 Due Today')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST               6 ('{"due":"today"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1926           LOAD_CONST               1 ('id')
                   LOAD_CONST               8 ('week')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST               9 ('📆 This Week')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST              10 ('{"due":"week"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1927           LOAD_CONST               1 ('id')
                   LOAD_CONST              11 ('overdue')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST              12 ('⚠️ Overdue')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST              13 ('{"due":"overdue"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1928           LOAD_CONST               1 ('id')
                   LOAD_CONST              14 ('my-tasks')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST              15 ('👤 My Tasks')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST              16 ('{"assignee":"me"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1929           LOAD_CONST               1 ('id')
                   LOAD_CONST              17 ('unassigned')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST              18 ('❓ Unassigned')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST              19 ('{"assignee":"unassigned"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1930           LOAD_CONST               1 ('id')
                   LOAD_CONST              20 ('high-priority')
                   LOAD_CONST               3 ('name')
                   LOAD_CONST              21 ('🔥 High Priority')
                   LOAD_CONST               5 ('filters')
                   LOAD_CONST              22 ('{"min_score":"70"}')
                   LOAD_CONST               7 ('is_default')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                4
    
    1924           BUILD_LIST               6
                   STORE_FAST               0 (default_filters)
    
    1932           LOAD_CONST              23 ('items')
                   LOAD_FAST_BORROW         0 (default_filters)
                   LOAD_CONST              24 ('total')
                   LOAD_GLOBAL              1 (len + NULL)
                   LOAD_FAST_BORROW         0 (default_filters)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/priorities/advanced")
async def advanced_filter(q, due, assignee, project, status, min_score, max_score, tags, sort, order, limit, offset):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:1942
    
      --             MAKE_CELL               30 (tag_list)
    
    1942             RETURN_GENERATOR
                     POP_TOP
             L1:     RESUME                   0
    
    1960             LOAD_SMALL_INT           0
                     LOAD_CONST               1 (('PriorityAnalyzer',))
                     IMPORT_NAME              0 (lib.analyzers.priority)
                     IMPORT_FROM              1 (PriorityAnalyzer)
                     STORE_FAST              12 (PriorityAnalyzer)
                     POP_TOP
    
    1963             LOAD_FAST_BORROW        12 (PriorityAnalyzer)
                     PUSH_NULL
                     LOAD_GLOBAL              4 (store)
                     LOAD_CONST               2 (('store',))
                     CALL_KW                  1
                     STORE_FAST              13 (analyzer)
    
    1964             LOAD_FAST_BORROW        13 (analyzer)
                     LOAD_ATTR                7 (analyze + NULL|self)
                     CALL                     0
                     STORE_FAST              14 (all_items)
    
    1966             LOAD_FAST               14 (all_items)
                     STORE_FAST              15 (filtered)
    
    1969             LOAD_FAST_BORROW         0 (q)
                     TO_BOOL
                     POP_JUMP_IF_FALSE       82 (to L11)
                     NOT_TAKEN
    
    1970             LOAD_FAST_BORROW         0 (q)
                     LOAD_ATTR                9 (lower + NULL|self)
                     CALL                     0
                     STORE_FAST              16 (q_lower)
    
    1971             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
             L2:     BUILD_LIST               0
                     SWAP                     2
             L3:     FOR_ITER                53 (to L9)
                     STORE_FAST              17 (i)
                     LOAD_FAST               16 (q_lower)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               3 ('title')
                     CALL                     1
                     COPY                     1
                     TO_BOOL
                     POP_JUMP_IF_TRUE         3 (to L6)
             L4:     NOT_TAKEN
             L5:     POP_TOP
                     LOAD_CONST               4 ('')
             L6:     LOAD_ATTR                9 (lower + NULL|self)
                     CALL                     0
                     CONTAINS_OP              0 (in)
             L7:     POP_JUMP_IF_TRUE         3 (to L8)
                     NOT_TAKEN
                     JUMP_BACKWARD           51 (to L3)
             L8:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           55 (to L3)
             L9:     END_FOR
                     POP_ITER
            L10:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
    
    1974    L11:     LOAD_FAST_BORROW         1 (due)
                     TO_BOOL
                     EXTENDED_ARG             2
                     POP_JUMP_IF_FALSE      630 (to L70)
            L12:     NOT_TAKEN
    
    1975    L13:     LOAD_GLOBAL             12 (datetime)
                     LOAD_ATTR               14 (now)
                     PUSH_NULL
                     CALL                     0
                     LOAD_ATTR               17 (date + NULL|self)
                     CALL                     0
                     STORE_FAST              18 (today)
    
    1977             LOAD_FAST_BORROW         1 (due)
                     LOAD_CONST               5 ('today')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       84 (to L22)
                     NOT_TAKEN
    
    1978             LOAD_FAST_BORROW        18 (today)
                     LOAD_ATTR               19 (isoformat + NULL|self)
                     CALL                     0
                     STORE_FAST              19 (today_str)
    
    1979             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L14:     BUILD_LIST               0
                     SWAP                     2
            L15:     FOR_ITER                53 (to L20)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L16:     POP_JUMP_IF_TRUE         3 (to L17)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L15)
            L17:     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST               6 ('due')
                     BINARY_OP               26 ([])
                     LOAD_CONST               7 (slice(None, 10, None))
                     BINARY_OP               26 ([])
                     LOAD_FAST_BORROW        19 (today_str)
                     COMPARE_OP              88 (bool(==))
            L18:     POP_JUMP_IF_TRUE         3 (to L19)
                     NOT_TAKEN
                     JUMP_BACKWARD           51 (to L15)
            L19:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           55 (to L15)
            L20:     END_FOR
                     POP_ITER
            L21:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     EXTENDED_ARG             1
                     JUMP_FORWARD           504 (to L70)
    
    1980    L22:     LOAD_FAST_BORROW         1 (due)
                     LOAD_CONST               8 ('tomorrow')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE      101 (to L31)
                     NOT_TAKEN
    
    1981             LOAD_FAST_BORROW        18 (today)
                     LOAD_GLOBAL             21 (timedelta + NULL)
                     LOAD_SMALL_INT           1
                     LOAD_CONST               9 (('days',))
                     CALL_KW                  1
                     BINARY_OP                0 (+)
                     LOAD_ATTR               19 (isoformat + NULL|self)
                     CALL                     0
                     STORE_FAST              20 (tomorrow_str)
    
    1982             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L23:     BUILD_LIST               0
                     SWAP                     2
            L24:     FOR_ITER                53 (to L29)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L25:     POP_JUMP_IF_TRUE         3 (to L26)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L24)
            L26:     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST               6 ('due')
                     BINARY_OP               26 ([])
                     LOAD_CONST               7 (slice(None, 10, None))
                     BINARY_OP               26 ([])
                     LOAD_FAST_BORROW        20 (tomorrow_str)
                     COMPARE_OP              88 (bool(==))
            L27:     POP_JUMP_IF_TRUE         3 (to L28)
                     NOT_TAKEN
                     JUMP_BACKWARD           51 (to L24)
            L28:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           55 (to L24)
            L29:     END_FOR
                     POP_ITER
            L30:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     EXTENDED_ARG             1
                     JUMP_FORWARD           397 (to L70)
    
    1983    L31:     LOAD_FAST_BORROW         1 (due)
                     LOAD_CONST              10 ('week')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE      101 (to L40)
                     NOT_TAKEN
    
    1984             LOAD_FAST_BORROW        18 (today)
                     LOAD_GLOBAL             21 (timedelta + NULL)
                     LOAD_SMALL_INT           7
                     LOAD_CONST               9 (('days',))
                     CALL_KW                  1
                     BINARY_OP                0 (+)
                     LOAD_ATTR               19 (isoformat + NULL|self)
                     CALL                     0
                     STORE_FAST              21 (week_end)
    
    1985             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L32:     BUILD_LIST               0
                     SWAP                     2
            L33:     FOR_ITER                53 (to L38)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L34:     POP_JUMP_IF_TRUE         3 (to L35)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L33)
            L35:     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST               6 ('due')
                     BINARY_OP               26 ([])
                     LOAD_CONST               7 (slice(None, 10, None))
                     BINARY_OP               26 ([])
                     LOAD_FAST_BORROW        21 (week_end)
                     COMPARE_OP              58 (bool(<=))
            L36:     POP_JUMP_IF_TRUE         3 (to L37)
                     NOT_TAKEN
                     JUMP_BACKWARD           51 (to L33)
            L37:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           55 (to L33)
            L38:     END_FOR
                     POP_ITER
            L39:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     EXTENDED_ARG             1
                     JUMP_FORWARD           290 (to L70)
    
    1986    L40:     LOAD_FAST_BORROW         1 (due)
                     LOAD_CONST              11 ('overdue')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       83 (to L49)
                     NOT_TAKEN
    
    1987             LOAD_FAST_BORROW        18 (today)
                     LOAD_ATTR               19 (isoformat + NULL|self)
                     CALL                     0
                     STORE_FAST              19 (today_str)
    
    1988             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L41:     BUILD_LIST               0
                     SWAP                     2
            L42:     FOR_ITER                53 (to L47)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L43:     POP_JUMP_IF_TRUE         3 (to L44)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L42)
            L44:     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST               6 ('due')
                     BINARY_OP               26 ([])
                     LOAD_CONST               7 (slice(None, 10, None))
                     BINARY_OP               26 ([])
                     LOAD_FAST_BORROW        19 (today_str)
                     COMPARE_OP              18 (bool(<))
            L45:     POP_JUMP_IF_TRUE         3 (to L46)
                     NOT_TAKEN
                     JUMP_BACKWARD           51 (to L42)
            L46:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           55 (to L42)
            L47:     END_FOR
                     POP_ITER
            L48:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     JUMP_FORWARD           201 (to L70)
    
    1989    L49:     LOAD_FAST_BORROW         1 (due)
                     LOAD_CONST              12 ('no_date')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       44 (to L56)
                     NOT_TAKEN
    
    1990             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L50:     BUILD_LIST               0
                     SWAP                     2
            L51:     FOR_ITER                30 (to L54)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L52:     POP_JUMP_IF_FALSE        3 (to L53)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L51)
            L53:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           32 (to L51)
            L54:     END_FOR
                     POP_ITER
            L55:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     JUMP_FORWARD           151 (to L70)
    
    1991    L56:     LOAD_FAST_BORROW         1 (due)
                     LOAD_ATTR               23 (startswith + NULL|self)
                     LOAD_CONST              13 ('range:')
                     CALL                     1
                     TO_BOOL
                     POP_JUMP_IF_FALSE      129 (to L70)
            L57:     NOT_TAKEN
    
    1993    L58:     LOAD_FAST_BORROW         1 (due)
                     LOAD_ATTR               25 (split + NULL|self)
                     LOAD_CONST              14 (':')
                     CALL                     1
                     STORE_FAST              22 (parts)
    
    1994             LOAD_GLOBAL             27 (len + NULL)
                     LOAD_FAST_BORROW        22 (parts)
                     CALL                     1
                     LOAD_SMALL_INT           3
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       96 (to L70)
                     NOT_TAKEN
    
    1995             LOAD_FAST_BORROW        22 (parts)
                     LOAD_SMALL_INT           1
                     BINARY_OP               26 ([])
                     LOAD_FAST_BORROW        22 (parts)
                     LOAD_SMALL_INT           2
                     BINARY_OP               26 ([])
                     STORE_FAST              24 (end_date)
                     STORE_FAST              23 (start_date)
    
    1996             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L59:     BUILD_LIST               0
                     SWAP                     2
            L60:     FOR_ITER                65 (to L68)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST               6 ('due')
                     CALL                     1
                     TO_BOOL
            L61:     POP_JUMP_IF_TRUE         3 (to L62)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L60)
            L62:     LOAD_FAST_BORROW        23 (start_date)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST               6 ('due')
                     BINARY_OP               26 ([])
                     LOAD_CONST               7 (slice(None, 10, None))
                     BINARY_OP               26 ([])
                     SWAP                     2
                     COPY                     2
                     COMPARE_OP              58 (bool(<=))
                     POP_JUMP_IF_FALSE       10 (to L65)
                     NOT_TAKEN
                     LOAD_FAST_BORROW        24 (end_date)
                     COMPARE_OP              58 (bool(<=))
            L63:     POP_JUMP_IF_TRUE         3 (to L64)
                     NOT_TAKEN
                     JUMP_BACKWARD           59 (to L60)
            L64:     JUMP_FORWARD             3 (to L67)
            L65:     POP_TOP
            L66:     JUMP_BACKWARD           63 (to L60)
            L67:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           67 (to L60)
            L68:     END_FOR
                     POP_ITER
            L69:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
    
    1999    L70:     LOAD_FAST_BORROW         2 (assignee)
                     TO_BOOL
                     POP_JUMP_IF_FALSE      245 (to L97)
            L71:     NOT_TAKEN
    
    2000    L72:     LOAD_FAST_BORROW         2 (assignee)
                     LOAD_ATTR                9 (lower + NULL|self)
                     CALL                     0
                     LOAD_CONST              15 ('unassigned')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       44 (to L79)
                     NOT_TAKEN
    
    2001             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L73:     BUILD_LIST               0
                     SWAP                     2
            L74:     FOR_ITER                30 (to L77)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST              16 ('assignee')
                     CALL                     1
                     TO_BOOL
            L75:     POP_JUMP_IF_FALSE        3 (to L76)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L74)
            L76:     LOAD_FAST_BORROW        17 (i)
                     LIST_APPEND              2
                     JUMP_BACKWARD           32 (to L74)
            L77:     END_FOR
                     POP_ITER
            L78:     STORE_FAST              15 (filtered)
                     STORE_FAST              17 (i)
                     JUMP_FORWARD           180 (to L97)
    
    2002    L79:     LOAD_FAST_BORROW         2 (assignee)
                     LOAD_ATTR                9 (lower + NULL|self)
                     CALL                     0
                     LOAD_CONST              17 ('me')
                     COMPARE_OP              88 (bool(==))
                     POP_JUMP_IF_FALSE       74 (to L88)
                     NOT_TAKEN
    
    2004             LOAD_FAST_BORROW        15 (filtered)
                     GET_ITER
                     LOAD_FAST_AND_CLEAR     17 (i)
                     SWAP                     2
            L80:     BUILD_LIST               0
                     SWAP                     2
            L81:     FOR_ITER                60 (to L86)
                     STORE_FAST              17 (i)
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_ATTR               11 (get + NULL|self)
                     LOAD_CONST              16 ('assignee')
                     CALL                     1
                     TO_BOOL
            L82:     POP_JUMP_IF_TRUE         3 (to L83)
                     NOT_TAKEN
                     JUMP_BACKWARD           28 (to L81)
            L83:     LOAD_CONST              17 ('me')
                     LOAD_FAST_BORROW        17 (i)
                     LOAD_CONST              16 ('assignee')
                     BINARY_OP               26 ([])
                     LOAD_ATTR                9 (lower + NULL|self)
                     CALL                     0
                     CONTAINS_OP            
    """
    raise NotImplementedError

@app.post("/api/priorities/archive-stale")
async def archive_stale(days):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2061
    
    2061           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2064           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('date', 'timedelta'))
                   IMPORT_NAME              0 (datetime)
                   IMPORT_FROM              1 (date)
                   STORE_FAST               1 (date)
                   IMPORT_FROM              2 (timedelta)
                   STORE_FAST               2 (timedelta)
                   POP_TOP
    
    2066           LOAD_FAST_BORROW         1 (date)
                   LOAD_ATTR                7 (today + NULL|self)
                   CALL                     0
                   LOAD_FAST_BORROW         2 (timedelta)
                   PUSH_NULL
                   LOAD_FAST_BORROW         0 (days)
                   LOAD_CONST               2 (('days',))
                   CALL_KW                  1
                   BINARY_OP               10 (-)
                   LOAD_ATTR                9 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               3 (cutoff)
    
    2069           LOAD_GLOBAL             10 (store)
                   LOAD_ATTR               13 (query + NULL|self)
    
    2070           LOAD_CONST               3 ("SELECT id FROM tasks WHERE status = 'pending' AND due_date IS NOT NULL AND due_date < ?")
    
    2071           LOAD_FAST_BORROW         3 (cutoff)
                   BUILD_LIST               1
    
    2069           CALL                     2
                   STORE_FAST               4 (stale)
    
    2075           LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR               14 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                9 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               5 (now)
    
    2076           LOAD_FAST_BORROW         4 (stale)
                   GET_ITER
           L2:     FOR_ITER                37 (to L3)
                   STORE_FAST               6 (task)
    
    2077           LOAD_GLOBAL             10 (store)
                   LOAD_ATTR               17 (update + NULL|self)
                   LOAD_CONST               4 ('tasks')
                   LOAD_FAST_BORROW         6 (task)
                   LOAD_CONST               5 ('id')
                   BINARY_OP               26 ([])
                   LOAD_CONST               6 ('status')
                   LOAD_CONST               7 ('archived')
                   LOAD_CONST               8 ('updated_at')
                   LOAD_FAST_BORROW         5 (now)
                   BUILD_MAP                2
                   CALL                     3
                   POP_TOP
                   JUMP_BACKWARD           39 (to L2)
    
    2076   L3:     END_FOR
                   POP_ITER
    
    2079           LOAD_GLOBAL             10 (store)
                   LOAD_ATTR               19 (clear_cache + NULL|self)
                   LOAD_CONST               9 ('priority_queue')
                   CALL                     1
                   POP_TOP
    
    2080           LOAD_CONST              10 ('success')
                   LOAD_CONST              11 (True)
                   LOAD_CONST               7 ('archived')
                   LOAD_GLOBAL             21 (len + NULL)
                   LOAD_FAST_BORROW         4 (stale)
                   CALL                     1
                   LOAD_CONST              12 ('cutoff')
                   LOAD_FAST_BORROW         3 (cutoff)
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/events")
async def get_events(hours):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2087
    
    2087           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2090           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get_upcoming_events + NULL|self)
                   LOAD_FAST_BORROW         0 (hours)
                   CALL                     1
                   STORE_FAST               1 (events)
    
    2091           LOAD_CONST               1 ('items')
                   LOAD_FAST_BORROW         1 (events)
                   LOAD_CONST               2 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         1 (events)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/day/{date}")
async def get_day_analysis(date):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2094
    
    2094           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2097           LOAD_FAST_BORROW         0 (date)
                   TO_BOOL
                   POP_JUMP_IF_FALSE       23 (to L2)
                   NOT_TAKEN
                   LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR                2 (fromisoformat)
                   PUSH_NULL
                   LOAD_FAST_BORROW         0 (date)
                   CALL                     1
                   JUMP_FORWARD            20 (to L3)
           L2:     LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR                4 (now)
                   PUSH_NULL
                   CALL                     0
           L3:     STORE_FAST               1 (target)
    
    2098           LOAD_GLOBAL              6 (analyzers)
                   LOAD_ATTR                8 (time)
                   LOAD_ATTR               11 (analyze_day + NULL|self)
                   LOAD_FAST_BORROW         1 (target)
                   CALL                     1
                   STORE_FAST               2 (analysis)
    
    2099           LOAD_FAST_BORROW         2 (analysis)
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/week")
async def get_week_analysis():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2102
    
    2102           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2105           LOAD_GLOBAL              0 (analyzers)
                   LOAD_ATTR                2 (time)
                   LOAD_ATTR                5 (get_week_summary + NULL|self)
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/emails")
async def get_emails(pending_only, actionable_only, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2112
    
    2112            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2115            LOAD_FAST_BORROW         1 (actionable_only)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       25 (to L2)
                    NOT_TAKEN
    
    2116            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
    
    2117            LOAD_CONST               1 ('SELECT * FROM communications WHERE requires_response = 1 AND processed = 0 ORDER BY created_at DESC LIMIT ?')
    
    2118            LOAD_FAST_BORROW         2 (limit)
                    BUILD_LIST               1
    
    2116            CALL                     2
                    STORE_FAST               3 (emails)
                    JUMP_FORWARD            55 (to L6)
    
    2120    L2:     LOAD_FAST_BORROW         0 (pending_only)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       25 (to L5)
            L3:     NOT_TAKEN
    
    2121    L4:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
    
    2122            LOAD_CONST               2 ('SELECT * FROM communications WHERE processed = 0 ORDER BY created_at DESC LIMIT ?')
    
    2123            LOAD_FAST_BORROW         2 (limit)
                    BUILD_LIST               1
    
    2121            CALL                     2
                    STORE_FAST               3 (emails)
                    JUMP_FORWARD            23 (to L6)
    
    2126    L5:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
    
    2127            LOAD_CONST               3 ('SELECT * FROM communications ORDER BY created_at DESC LIMIT ?')
    
    2128            LOAD_FAST_BORROW         2 (limit)
                    BUILD_LIST               1
    
    2126            CALL                     2
                    STORE_FAST               3 (emails)
    
    2132    L6:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                5 (count + NULL|self)
                    LOAD_CONST               4 ('communications')
                    LOAD_CONST               5 ('requires_response = 1 AND processed = 0')
                    CALL                     2
                    STORE_FAST               4 (actionable_count)
    
    2135            LOAD_CONST               6 ('items')
                    LOAD_FAST_BORROW         3 (emails)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (e)
                    SWAP                     2
            L7:     BUILD_LIST               0
                    SWAP                     2
            L8:     FOR_ITER                14 (to L9)
                    STORE_FAST               5 (e)
                    LOAD_GLOBAL              7 (dict + NULL)
                    LOAD_FAST_BORROW         5 (e)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L8)
            L9:     END_FOR
                    POP_ITER
           L10:     SWAP                     2
                    STORE_FAST               5 (e)
    
    2136            LOAD_CONST               7 ('total')
                    LOAD_GLOBAL              9 (len + NULL)
                    LOAD_FAST_BORROW         3 (emails)
                    CALL                     1
    
    2137            LOAD_CONST               8 ('actionable_count')
                    LOAD_FAST_BORROW         4 (actionable_count)
    
    2134            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L11:     SWAP                     2
                    POP_TOP
    
    2135            SWAP                     2
                    STORE_FAST               5 (e)
                    RERAISE                  0
    
      --   L12:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L12 [0] lasti
      L4 to L7 -> L12 [0] lasti
      L7 to L10 -> L11 [3]
      L10 to L12 -> L12 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/emails/{email_id}/mark-actionable")
async def mark_email_actionable(email_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2141
    
    2141           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2144           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               1 ('communications')
                   LOAD_FAST_BORROW         0 (email_id)
                   CALL                     2
                   STORE_FAST               1 (email)
    
    2145           LOAD_FAST_BORROW         1 (email)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
    2146           LOAD_GLOBAL              5 (HTTPException + NULL)
                   LOAD_CONST               2 (404)
                   LOAD_CONST               3 ('Email not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
    2148   L2:     LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                7 (update + NULL|self)
                   LOAD_CONST               1 ('communications')
                   LOAD_FAST_BORROW         0 (email_id)
    
    2149           LOAD_CONST               4 ('requires_response')
                   LOAD_SMALL_INT           1
    
    2148           BUILD_MAP                1
                   CALL                     3
                   POP_TOP
    
    2151           LOAD_CONST               5 ('success')
                   LOAD_CONST               6 (True)
                   LOAD_CONST               7 ('id')
                   LOAD_FAST_BORROW         0 (email_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/insights")
async def get_insights(domain):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2158
    
    2158            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2161            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get_active_insights + NULL|self)
                    CALL                     0
                    STORE_FAST               1 (insights)
    
    2162            LOAD_FAST_BORROW         0 (domain)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       33 (to L8)
                    NOT_TAKEN
    
    2163            LOAD_FAST_BORROW         1 (insights)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      2 (i)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                20 (to L6)
                    STORE_FAST_LOAD_FAST    34 (i, i)
                    LOAD_CONST               1 ('domain')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW         0 (domain)
                    COMPARE_OP              88 (bool(==))
            L4:     POP_JUMP_IF_TRUE         3 (to L5)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L3)
            L5:     LOAD_FAST_BORROW         2 (i)
                    LIST_APPEND              2
                    JUMP_BACKWARD           22 (to L3)
            L6:     END_FOR
                    POP_ITER
            L7:     STORE_FAST               1 (insights)
                    STORE_FAST               2 (i)
    
    2164    L8:     LOAD_CONST               2 ('items')
                    LOAD_FAST_BORROW         1 (insights)
                    LOAD_CONST               3 ('total')
                    LOAD_GLOBAL              5 (len + NULL)
                    LOAD_FAST_BORROW         1 (insights)
                    CALL                     1
                    BUILD_MAP                2
                    RETURN_VALUE
    
      --    L9:     SWAP                     2
                    POP_TOP
    
    2163            SWAP                     2
                    STORE_FAST               2 (i)
                    RERAISE                  0
    
      --   L10:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L10 [0] lasti
      L2 to L4 -> L9 [2]
      L5 to L7 -> L9 [2]
      L7 to L10 -> L10 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/anomalies")
async def get_anomalies():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2167
    
    2167           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2170           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get_cache + NULL|self)
                   LOAD_CONST               1 ('anomalies')
                   CALL                     1
                   COPY                     1
                   TO_BOOL
                   POP_JUMP_IF_TRUE         3 (to L2)
                   NOT_TAKEN
                   POP_TOP
                   BUILD_LIST               0
           L2:     STORE_FAST               0 (anomalies)
    
    2171           LOAD_CONST               2 ('items')
                   LOAD_FAST_BORROW         0 (anomalies)
                   LOAD_CONST               3 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         0 (anomalies)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/notifications")
async def get_notifications(pending_only, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2178
    
    2178           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2181           LOAD_FAST_BORROW         0 (pending_only)
                   TO_BOOL
                   POP_JUMP_IF_FALSE       25 (to L2)
                   NOT_TAKEN
    
    2182           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    2183           LOAD_CONST               1 ('SELECT * FROM notifications WHERE sent_at IS NULL ORDER BY created_at DESC LIMIT ?')
    
    2184           LOAD_FAST_BORROW         1 (limit)
                   BUILD_LIST               1
    
    2182           CALL                     2
                   STORE_FAST               2 (notifications)
                   JUMP_FORWARD            23 (to L3)
    
    2187   L2:     LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    2188           LOAD_CONST               2 ('SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?')
    
    2189           LOAD_FAST_BORROW         1 (limit)
                   BUILD_LIST               1
    
    2187           CALL                     2
                   STORE_FAST               2 (notifications)
    
    2191   L3:     LOAD_CONST               3 ('items')
                   LOAD_FAST_BORROW         2 (notifications)
                   LOAD_CONST               4 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         2 (notifications)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/notifications/stats")
async def get_notification_stats():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2194
    
    2194           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2197           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('NotificationEngine',))
                   IMPORT_NAME              0 (lib.notifier.engine)
                   IMPORT_FROM              1 (NotificationEngine)
                   STORE_FAST               0 (NotificationEngine)
                   POP_TOP
    
    2198           LOAD_FAST_BORROW         0 (NotificationEngine)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   BUILD_MAP                0
                   CALL                     2
                   STORE_FAST               1 (engine)
    
    2201           LOAD_CONST               2 ('pending')
                   LOAD_FAST_BORROW         1 (engine)
                   LOAD_ATTR                7 (get_pending_count + NULL|self)
                   CALL                     0
    
    2202           LOAD_CONST               3 ('sent_today')
                   LOAD_FAST_BORROW         1 (engine)
                   LOAD_ATTR                9 (get_sent_today + NULL|self)
                   CALL                     0
    
    2200           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2206
    
    2206           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2209           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (update + NULL|self)
                   LOAD_CONST               1 ('notifications')
                   LOAD_FAST_BORROW         0 (notif_id)
    
    2210           LOAD_CONST               2 ('sent_at')
                   LOAD_GLOBAL              4 (datetime)
                   LOAD_ATTR                6 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                9 (isoformat + NULL|self)
                   CALL                     0
    
    2211           LOAD_CONST               3 ('status')
                   LOAD_CONST               4 ('dismissed')
    
    2209           BUILD_MAP                2
                   CALL                     3
                   POP_TOP
    
    2213           LOAD_CONST               5 ('success')
                   LOAD_CONST               6 (True)
                   LOAD_CONST               7 ('id')
                   LOAD_FAST_BORROW         0 (notif_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/notifications/dismiss-all")
async def dismiss_all_notifications():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2216
    
    2216           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2219           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
                   LOAD_CONST               1 ('SELECT id FROM notifications WHERE sent_at IS NULL')
                   CALL                     1
                   STORE_FAST               0 (pending)
    
    2220           LOAD_GLOBAL              4 (datetime)
                   LOAD_ATTR                6 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                9 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               1 (now)
    
    2222           LOAD_FAST_BORROW         0 (pending)
                   GET_ITER
           L2:     FOR_ITER                37 (to L3)
                   STORE_FAST               2 (notif)
    
    2223           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR               11 (update + NULL|self)
                   LOAD_CONST               2 ('notifications')
                   LOAD_FAST_BORROW         2 (notif)
                   LOAD_CONST               3 ('id')
                   BINARY_OP               26 ([])
    
    2224           LOAD_CONST               4 ('sent_at')
                   LOAD_FAST_BORROW         1 (now)
    
    2225           LOAD_CONST               5 ('status')
                   LOAD_CONST               6 ('dismissed')
    
    2223           BUILD_MAP                2
                   CALL                     3
                   POP_TOP
                   JUMP_BACKWARD           39 (to L2)
    
    2222   L3:     END_FOR
                   POP_ITER
    
    2228           LOAD_CONST               7 ('success')
                   LOAD_CONST               8 (True)
                   LOAD_CONST               6 ('dismissed')
                   LOAD_GLOBAL             13 (len + NULL)
                   LOAD_FAST_BORROW         0 (pending)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/approvals")
async def get_approvals():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2235
    
    2235           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2238           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get_pending_decisions + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (decisions)
    
    2239           LOAD_CONST               1 ('items')
                   LOAD_FAST_BORROW         0 (decisions)
                   LOAD_CONST               2 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         0 (decisions)
                   CALL                     1
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/approvals/{decision_id}")
async def process_approval(decision_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2242
    
    2242            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2245            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('decisions')
                    LOAD_FAST_BORROW         0 (decision_id)
                    CALL                     2
                    STORE_FAST               2 (decision)
    
    2246            LOAD_FAST_BORROW         2 (decision)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    2247            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Decision not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    2249    L2:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                6 (action)
                    LOAD_CONST               4 ('approve')
                    COMPARE_OP              72 (==)
                    STORE_FAST               3 (approved)
    
    2250            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                9 (update + NULL|self)
                    LOAD_CONST               1 ('decisions')
                    LOAD_FAST                0 (decision_id)
    
    2251            LOAD_CONST               5 ('approved')
                    LOAD_FAST_BORROW         3 (approved)
                    TO_BOOL
                    POP_JUMP_IF_FALSE        3 (to L5)
            L3:     NOT_TAKEN
            L4:     LOAD_SMALL_INT           1
                    JUMP_FORWARD             1 (to L6)
            L5:     LOAD_SMALL_INT           0
    
    2252    L6:     LOAD_CONST               6 ('approved_at')
                    LOAD_GLOBAL             10 (datetime)
                    LOAD_ATTR               12 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               15 (isoformat + NULL|self)
                    CALL                     0
    
    2250            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    2256            LOAD_CONST               7 ('status')
                    LOAD_FAST_BORROW         3 (approved)
                    TO_BOOL
                    POP_JUMP_IF_FALSE        6 (to L9)
            L7:     NOT_TAKEN
            L8:     LOAD_CONST               5 ('approved')
    
    2257            LOAD_CONST               9 ('decision_id')
                    LOAD_FAST_BORROW         0 (decision_id)
    
    2255            BUILD_MAP                2
                    RETURN_VALUE
    
    2256    L9:     LOAD_CONST               8 ('rejected')
    
    2257            LOAD_CONST               9 ('decision_id')
                    LOAD_FAST_BORROW         0 (decision_id)
    
    2255            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L10:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L10 [0] lasti
      L4 to L7 -> L10 [0] lasti
      L8 to L10 -> L10 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/approvals/{decision_id}/modify")
async def modify_approval(decision_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2265
    
    2265           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2268           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               1 ('decisions')
                   LOAD_FAST_BORROW         0 (decision_id)
                   CALL                     2
                   STORE_FAST               2 (decision)
    
    2269           LOAD_FAST_BORROW         2 (decision)
                   TO_BOOL
                   POP_JUMP_IF_TRUE        13 (to L2)
                   NOT_TAKEN
    
    2270           LOAD_GLOBAL              5 (HTTPException + NULL)
                   LOAD_CONST               2 (404)
                   LOAD_CONST               3 ('Decision not found')
                   CALL                     2
                   RAISE_VARARGS            1
    
    2273   L2:     LOAD_GLOBAL              6 (json)
                   LOAD_ATTR                8 (loads)
                   PUSH_NULL
                   LOAD_FAST_BORROW         2 (decision)
                   LOAD_ATTR                3 (get + NULL|self)
                   LOAD_CONST               4 ('input_data')
                   LOAD_CONST               5 ('{}')
                   CALL                     2
                   CALL                     1
                   STORE_FAST               3 (input_data)
    
    2274           LOAD_FAST_BORROW         3 (input_data)
                   LOAD_ATTR               11 (update + NULL|self)
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (modifications)
                   CALL                     1
                   POP_TOP
    
    2276           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR               11 (update + NULL|self)
                   LOAD_CONST               1 ('decisions')
                   LOAD_FAST_BORROW         0 (decision_id)
    
    2277           LOAD_CONST               4 ('input_data')
                   LOAD_GLOBAL              6 (json)
                   LOAD_ATTR               14 (dumps)
                   PUSH_NULL
                   LOAD_FAST_BORROW         3 (input_data)
                   CALL                     1
    
    2278           LOAD_CONST               6 ('rationale')
                   LOAD_CONST               7 ('Modified: ')
                   LOAD_GLOBAL             17 (list + NULL)
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (modifications)
                   LOAD_ATTR               19 (keys + NULL|self)
                   CALL                     0
                   CALL                     1
                   FORMAT_SIMPLE
                   BUILD_STRING             2
    
    2276           BUILD_MAP                2
                   CALL                     3
                   POP_TOP
    
    2282           LOAD_CONST               8 ('status')
                   LOAD_CONST               9 ('modified')
    
    2283           LOAD_CONST              10 ('decision_id')
                   LOAD_FAST_BORROW         0 (decision_id)
    
    2284           LOAD_CONST              11 ('modifications')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR               12 (modifications)
    
    2281           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/governance")
async def get_governance_status():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2292
    
    2292            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2295            LOAD_GLOBAL              0 (governance)
                    LOAD_ATTR                3 (get_status + NULL|self)
                    CALL                     0
                    STORE_FAST               0 (status)
    
    2298            LOAD_GLOBAL              4 (store)
                    LOAD_ATTR                7 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT phase, COUNT(*) as count, MAX(created_at) as last_action\n        FROM cycle_logs \n        WHERE created_at > datetime('now', '-24 hours')\n        GROUP BY phase\n    ")
                    CALL                     1
                    STORE_FAST               1 (recent_actions)
    
    2307            LOAD_FAST_BORROW         1 (recent_actions)
                    GET_ITER
    
    2305            LOAD_FAST_AND_CLEAR      2 (a)
                    SWAP                     2
            L2:     BUILD_MAP                0
                    SWAP                     2
    
    2307    L3:     FOR_ITER                31 (to L4)
                    STORE_FAST               2 (a)
    
    2306            LOAD_FAST_BORROW         2 (a)
                    LOAD_CONST               2 ('phase')
                    BINARY_OP               26 ([])
                    LOAD_CONST               3 ('count')
                    LOAD_FAST_BORROW         2 (a)
                    LOAD_CONST               3 ('count')
                    BINARY_OP               26 ([])
                    LOAD_CONST               4 ('last')
                    LOAD_FAST_BORROW         2 (a)
                    LOAD_CONST               5 ('last_action')
                    BINARY_OP               26 ([])
                    BUILD_MAP                2
                    MAP_ADD                  2
                    JUMP_BACKWARD           33 (to L3)
    
    2307    L4:     END_FOR
                    POP_ITER
    
    2305    L5:     SWAP                     2
                    STORE_FAST               2 (a)
                    LOAD_FAST_BORROW         0 (status)
                    LOAD_CONST               6 ('recent_actions')
                    STORE_SUBSCR
    
    2311            LOAD_GLOBAL              4 (store)
                    LOAD_ATTR                7 (query + NULL|self)
                    LOAD_CONST               7 ('\n        SELECT domain, COUNT(*) as count\n        FROM decisions\n        WHERE approved IS NULL\n        GROUP BY domain\n    ')
                    CALL                     1
                    STORE_FAST               3 (pending)
    
    2317            LOAD_FAST_BORROW         3 (pending)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      4 (p)
                    SWAP                     2
            L6:     BUILD_MAP                0
                    SWAP                     2
            L7:     FOR_ITER                19 (to L8)
                    STORE_FAST_LOAD_FAST    68 (p, p)
                    LOAD_CONST               8 ('domain')
                    BINARY_OP               26 ([])
                    LOAD_FAST_BORROW         4 (p)
                    LOAD_CONST               3 ('count')
                    BINARY_OP               26 ([])
                    MAP_ADD                  2
                    JUMP_BACKWARD           21 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               4 (p)
                    LOAD_FAST_BORROW         0 (status)
                    LOAD_CONST               9 ('pending_by_domain')
                    STORE_SUBSCR
    
    2319            LOAD_FAST_BORROW         0 (status)
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
    2305            SWAP                     2
                    STORE_FAST               2 (a)
                    RERAISE                  0
    
      --   L11:     SWAP                     2
                    POP_TOP
    
    2317            SWAP                     2
                    STORE_FAST               4 (p)
                    RERAISE                  0
    
      --   L12:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L12 [0] lasti
      L2 to L5 -> L10 [2]
      L5 to L6 -> L12 [0] lasti
      L6 to L9 -> L11 [2]
      L9 to L12 -> L12 [0] lasti
    """
    raise NotImplementedError

@app.put("/api/governance/{domain}")
async def set_governance_mode(domain, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2322
    
    2322           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2325   L2:     NOP
    
    2326   L3:     LOAD_GLOBAL              1 (DomainMode + NULL)
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR                2 (mode)
                   CALL                     1
                   STORE_FAST               2 (mode)
    
    2330   L4:     LOAD_GLOBAL              8 (governance)
                   LOAD_ATTR               11 (set_mode + NULL|self)
                   LOAD_FAST_LOAD_FAST      2 (domain, mode)
                   CALL                     2
                   POP_TOP
    
    2333           LOAD_GLOBAL             12 (store)
                   LOAD_ATTR               15 (insert + NULL|self)
                   LOAD_CONST               3 ('cycle_logs')
    
    2334           LOAD_CONST               4 ('id')
                   LOAD_CONST               5 ('gov_change_')
                   LOAD_GLOBAL             16 (datetime)
                   LOAD_ATTR               18 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               21 (isoformat + NULL|self)
                   CALL                     0
                   FORMAT_SIMPLE
                   BUILD_STRING             2
    
    2335           LOAD_CONST               6 ('cycle_number')
                   LOAD_SMALL_INT           0
    
    2336           LOAD_CONST               7 ('phase')
                   LOAD_CONST               8 ('governance_change')
    
    2337           LOAD_CONST               9 ('data')
                   LOAD_GLOBAL             22 (json)
                   LOAD_ATTR               24 (dumps)
                   PUSH_NULL
                   LOAD_CONST              10 ('domain')
                   LOAD_FAST                0 (domain)
                   LOAD_CONST              11 ('new_mode')
                   LOAD_FAST                1 (body)
                   LOAD_ATTR                2 (mode)
                   BUILD_MAP                2
                   CALL                     1
    
    2338           LOAD_CONST              12 ('created_at')
                   LOAD_GLOBAL             16 (datetime)
                   LOAD_ATTR               18 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR               21 (isoformat + NULL|self)
                   CALL                     0
    
    2333           BUILD_MAP                5
                   CALL                     2
                   POP_TOP
    
    2341           LOAD_CONST              10 ('domain')
                   LOAD_FAST                0 (domain)
                   LOAD_CONST              13 ('mode')
                   LOAD_FAST                1 (body)
                   LOAD_ATTR                2 (mode)
                   LOAD_CONST              14 ('status')
                   LOAD_CONST              15 ('updated')
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L5:     PUSH_EXC_INFO
    
    2327           LOAD_GLOBAL              4 (ValueError)
                   CHECK_EXC_MATCH
                   POP_JUMP_IF_FALSE       27 (to L6)
                   NOT_TAKEN
                   POP_TOP
    
    2328           LOAD_GLOBAL              7 (HTTPException + NULL)
                   LOAD_CONST               1 (400)
                   LOAD_CONST               2 ('Invalid mode: ')
                   LOAD_FAST                1 (body)
                   LOAD_ATTR                2 (mode)
                   FORMAT_SIMPLE
                   BUILD_STRING             2
                   CALL                     2
                   RAISE_VARARGS            1
    
    2327   L6:     RERAISE                  0
    
      --   L7:     COPY                     3
                   POP_EXCEPT
                   RERAISE                  1
           L8:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L8 [0] lasti
      L3 to L4 -> L5 [0]
      L4 to L5 -> L8 [0] lasti
      L5 to L7 -> L7 [1] lasti
      L7 to L8 -> L8 [0] lasti
    """
    raise NotImplementedError

@app.put("/api/governance/{domain}/threshold")
async def set_governance_threshold(domain, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2348
    
    2348           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2351           LOAD_SMALL_INT           0
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR                0 (threshold)
                   SWAP                     2
                   COPY                     2
                   COMPARE_OP              58 (bool(<=))
                   POP_JUMP_IF_FALSE        8 (to L2)
                   NOT_TAKEN
                   LOAD_SMALL_INT           1
                   COMPARE_OP              58 (bool(<=))
                   POP_JUMP_IF_TRUE        15 (to L4)
                   NOT_TAKEN
                   JUMP_FORWARD             1 (to L3)
           L2:     POP_TOP
    
    2352   L3:     LOAD_GLOBAL              3 (HTTPException + NULL)
                   LOAD_CONST               1 (400)
                   LOAD_CONST               2 ('Threshold must be between 0 and 1')
                   CALL                     2
                   RAISE_VARARGS            1
    
    2355   L4:     LOAD_CONST               3 ('domains')
                   LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                6 (config)
                   CONTAINS_OP              1 (not in)
                   POP_JUMP_IF_FALSE       20 (to L5)
                   NOT_TAKEN
    
    2356           BUILD_MAP                0
                   LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                6 (config)
                   LOAD_CONST               3 ('domains')
                   STORE_SUBSCR
    
    2357   L5:     LOAD_FAST_BORROW         0 (domain)
                   LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                6 (config)
                   LOAD_CONST               3 ('domains')
                   BINARY_OP               26 ([])
                   CONTAINS_OP              1 (not in)
                   POP_JUMP_IF_FALSE       27 (to L6)
                   NOT_TAKEN
    
    2358           BUILD_MAP                0
                   LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                6 (config)
                   LOAD_CONST               3 ('domains')
                   BINARY_OP               26 ([])
                   LOAD_FAST_BORROW         0 (domain)
                   STORE_SUBSCR
    
    2360   L6:     LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR                0 (threshold)
                   LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                6 (config)
                   LOAD_CONST               3 ('domains')
                   BINARY_OP               26 ([])
                   LOAD_FAST_BORROW         0 (domain)
                   BINARY_OP               26 ([])
                   LOAD_CONST               4 ('auto_threshold')
                   STORE_SUBSCR
    
    2361           LOAD_GLOBAL              4 (governance)
                   LOAD_ATTR                9 (_save_config + NULL|self)
                   CALL                     0
                   POP_TOP
    
    2363           LOAD_CONST               5 ('domain')
                   LOAD_FAST_BORROW         0 (domain)
                   LOAD_CONST               6 ('threshold')
                   LOAD_FAST_BORROW         1 (body)
                   LOAD_ATTR                0 (threshold)
                   LOAD_CONST               7 ('status')
                   LOAD_CONST               8 ('updated')
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/governance/history")
async def get_governance_history(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2366
    
    2366            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2369            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT * FROM cycle_logs\n        WHERE phase IN ('governance_change', 'emergency_brake', 'action_executed', 'action_blocked')\n        ORDER BY created_at DESC\n        LIMIT ?\n    ")
    
    2374            LOAD_FAST_BORROW         0 (limit)
                    BUILD_LIST               1
    
    2369            CALL                     2
                    STORE_FAST               1 (history)
    
    2377            LOAD_CONST               2 ('items')
    
    2382            LOAD_FAST_BORROW         1 (history)
                    GET_ITER
    
    2377            LOAD_FAST_AND_CLEAR      2 (h)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
    
    2382    L3:     FOR_ITER                78 (to L8)
                    STORE_FAST               2 (h)
    
    2378            LOAD_CONST               3 ('id')
                    LOAD_FAST_BORROW         2 (h)
                    LOAD_CONST               3 ('id')
                    BINARY_OP               26 ([])
    
    2379            LOAD_CONST               4 ('phase')
                    LOAD_FAST_BORROW         2 (h)
                    LOAD_CONST               4 ('phase')
                    BINARY_OP               26 ([])
    
    2380            LOAD_CONST               5 ('data')
                    LOAD_FAST_BORROW         2 (h)
                    LOAD_CONST               5 ('data')
                    BINARY_OP               26 ([])
                    TO_BOOL
                    POP_JUMP_IF_FALSE       30 (to L6)
            L4:     NOT_TAKEN
            L5:     LOAD_GLOBAL              4 (json)
                    LOAD_ATTR                6 (loads)
                    PUSH_NULL
                    LOAD_FAST_BORROW         2 (h)
                    LOAD_CONST               5 ('data')
                    BINARY_OP               26 ([])
                    CALL                     1
                    JUMP_FORWARD             1 (to L7)
            L6:     BUILD_MAP                0
    
    2381    L7:     LOAD_CONST               6 ('timestamp')
                    LOAD_FAST_BORROW         2 (h)
                    LOAD_CONST               7 ('created_at')
                    BINARY_OP               26 ([])
    
    2377            BUILD_MAP                4
                    LIST_APPEND              2
                    JUMP_BACKWARD           80 (to L3)
    
    2382    L8:     END_FOR
                    POP_ITER
    
    2377    L9:     SWAP                     2
                    STORE_FAST               2 (h)
    
    2383            LOAD_CONST               8 ('total')
                    LOAD_GLOBAL              9 (len + NULL)
                    LOAD_FAST_BORROW         1 (history)
                    CALL                     1
    
    2376            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L10:     SWAP                     2
                    POP_TOP
    
    2377            SWAP                     2
                    STORE_FAST               2 (h)
                    RERAISE                  0
    
      --   L11:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L11 [0] lasti
      L2 to L4 -> L10 [3]
      L5 to L9 -> L10 [3]
      L9 to L11 -> L11 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/governance/emergency-brake")
async def activate_emergency_brake(reason):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2387
    
    2387           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2390           LOAD_GLOBAL              0 (governance)
                   LOAD_ATTR                3 (emergency_brake + NULL|self)
                   LOAD_FAST_BORROW         0 (reason)
                   CALL                     1
                   POP_TOP
    
    2392           LOAD_CONST               1 ('status')
                   LOAD_CONST               2 ('activated')
    
    2393           LOAD_CONST               3 ('reason')
                   LOAD_FAST_BORROW         0 (reason)
    
    2394           LOAD_CONST               4 ('message')
                   LOAD_CONST               5 ('All domains set to OBSERVE mode. No automatic actions will be taken.')
    
    2391           BUILD_MAP                3
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.delete("/api/governance/emergency-brake")
async def release_emergency_brake():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2398
    
    2398           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2401           LOAD_GLOBAL              0 (governance)
                   LOAD_ATTR                3 (release_brake + NULL|self)
                   CALL                     0
                   POP_TOP
    
    2403           LOAD_CONST               1 ('status')
                   LOAD_CONST               2 ('released')
    
    2404           LOAD_CONST               3 ('message')
                   LOAD_CONST               4 ('Emergency brake released. Domains remain in OBSERVE mode until manually changed.')
    
    2402           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/sync/status")
async def get_sync_status():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2415
    
    2415           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2418           LOAD_GLOBAL              0 (collectors)
                   LOAD_ATTR                3 (get_status + NULL|self)
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/sync")
async def force_sync(source):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2421
    
    2421           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2424           LOAD_GLOBAL              0 (collectors)
                   LOAD_ATTR                3 (force_sync + NULL|self)
                   LOAD_FAST_BORROW         0 (source)
                   CALL                     1
                   STORE_FAST               1 (result)
    
    2425           LOAD_FAST_BORROW         1 (result)
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/analyze")
async def run_analysis():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2428
    
    2428           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2431           LOAD_GLOBAL              0 (analyzers)
                   LOAD_ATTR                3 (analyze_all + NULL|self)
                   CALL                     0
                   STORE_FAST               0 (result)
    
    2432           LOAD_FAST_BORROW         0 (result)
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/cycle")
async def run_cycle():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2435
    
    2435           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2438           LOAD_GLOBAL              1 (AutonomousLoop + NULL)
                   CALL                     0
                   STORE_FAST               0 (loop)
    
    2439           LOAD_FAST_BORROW         0 (loop)
                   LOAD_ATTR                3 (run_cycle + NULL|self)
                   CALL                     0
                   STORE_FAST               1 (result)
    
    2440           LOAD_FAST_BORROW         1 (result)
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/status")
async def get_status():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2447
    
    2447           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2450           LOAD_GLOBAL              1 (AutonomousLoop + NULL)
                   CALL                     0
                   STORE_FAST               0 (loop)
    
    2451           LOAD_FAST_BORROW         0 (loop)
                   LOAD_ATTR                3 (get_status + NULL|self)
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/health")
async def health_check():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2454
    
    2454           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2458           LOAD_CONST               1 ('status')
                   LOAD_CONST               2 ('healthy')
    
    2459           LOAD_CONST               3 ('timestamp')
                   LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR                2 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                5 (isoformat + NULL|self)
                   CALL                     0
    
    2457           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/summary")
async def get_summary():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2467
    
    2467            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2470            LOAD_SMALL_INT           0
                    LOAD_CONST               1 (('date', 'timedelta'))
                    IMPORT_NAME              0 (datetime)
                    IMPORT_FROM              1 (date)
                    STORE_FAST               0 (date)
                    IMPORT_FROM              2 (timedelta)
                    STORE_FAST               1 (timedelta)
                    POP_TOP
    
    2472            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (get_cache + NULL|self)
                    LOAD_CONST               2 ('priority_queue')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L2)
                    NOT_TAKEN
                    POP_TOP
                    BUILD_LIST               0
            L2:     STORE_FAST               2 (queue)
    
    2473            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR                9 (get_cache + NULL|self)
                    LOAD_CONST               3 ('anomalies')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L5)
            L3:     NOT_TAKEN
            L4:     POP_TOP
                    BUILD_LIST               0
            L5:     STORE_FAST               3 (anomalies)
    
    2476            LOAD_FAST_BORROW         0 (date)
                    LOAD_ATTR               11 (today + NULL|self)
                    CALL                     0
                    LOAD_ATTR               13 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               4 (today)
    
    2477            LOAD_GLOBAL              6 (store)
                    LOAD_ATTR               15 (query + NULL|self)
    
    2478            LOAD_CONST               4 ('SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time')
    
    2479            LOAD_FAST_BORROW         4 (today)
                    BUILD_LIST               1
    
    2477            CALL                     2
                    STORE_FAST               5 (today_events)
    
    2483            LOAD_SMALL_INT           0
                    STORE_FAST               6 (total_event_hours)
    
    2484            LOAD_FAST_BORROW         5 (today_events)
                    GET_ITER
            L6:     FOR_ITER               130 (to L10)
                    STORE_FAST               7 (e)
    
    2485    L7:     NOP
    
    2486    L8:     LOAD_GLOBAL              0 (datetime)
                    LOAD_ATTR               16 (fromisoformat)
                    PUSH_NULL
                    LOAD_FAST_BORROW         7 (e)
                    LOAD_CONST               5 ('start_time')
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (replace + NULL|self)
                    LOAD_CONST               6 ('Z')
                    LOAD_CONST               7 ('+00:00')
                    CALL                     2
                    CALL                     1
                    STORE_FAST               8 (start)
    
    2487            LOAD_GLOBAL              0 (datetime)
                    LOAD_ATTR               16 (fromisoformat)
                    PUSH_NULL
                    LOAD_FAST_BORROW         7 (e)
                    LOAD_CONST               8 ('end_time')
                    BINARY_OP               26 ([])
                    LOAD_ATTR               19 (replace + NULL|self)
                    LOAD_CONST               6 ('Z')
                    LOAD_CONST               7 ('+00:00')
                    CALL                     2
                    CALL                     1
                    STORE_FAST               9 (end)
    
    2488            LOAD_FAST_BORROW_LOAD_FAST_BORROW 105 (total_event_hours, end)
                    LOAD_FAST_BORROW         8 (start)
                    BINARY_OP               10 (-)
                    LOAD_ATTR               21 (total_seconds + NULL|self)
                    CALL                     0
                    LOAD_CONST               9 (3600)
                    BINARY_OP               11 (/)
                    BINARY_OP               13 (+=)
                    STORE_FAST               6 (total_event_hours)
            L9:     JUMP_BACKWARD          132 (to L6)
    
    2484   L10:     END_FOR
                    POP_ITER
    
    2492            LOAD_SMALL_INT           9
                    STORE_FAST              10 (work_hours)
    
    2493            LOAD_GLOBAL             23 (max + NULL)
                    LOAD_SMALL_INT           0
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 166 (work_hours, total_event_hours)
                    BINARY_OP               10 (-)
                    CALL                     2
                    STORE_FAST              11 (available)
    
    2496            LOAD_CONST              10 ('priorities')
    
    2497            LOAD_CONST              11 ('top_5')
                    LOAD_FAST_BORROW         2 (queue)
                    LOAD_CONST              12 (slice(None, 5, None))
                    BINARY_OP               26 ([])
    
    2498            LOAD_CONST              13 ('total')
                    LOAD_GLOBAL             25 (len + NULL)
                    LOAD_FAST_BORROW         2 (queue)
                    CALL                     1
    
    2499            LOAD_CONST              14 ('critical_count')
                    LOAD_GLOBAL             25 (len + NULL)
                    LOAD_FAST_BORROW         2 (queue)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     12 (i)
                    SWAP                     2
           L11:     BUILD_LIST               0
                    SWAP                     2
           L12:     FOR_ITER                29 (to L15)
                    STORE_FAST_LOAD_FAST   204 (i, i)
                    LOAD_ATTR               27 (get + NULL|self)
                    LOAD_CONST              15 ('score')
                    LOAD_SMALL_INT           0
                    CALL                     2
                    LOAD_SMALL_INT          70
                    COMPARE_OP             188 (bool(>=))
           L13:     POP_JUMP_IF_TRUE         3 (to L14)
                    NOT_TAKEN
                    JUMP_BACKWARD           27 (to L12)
           L14:     LOAD_FAST_BORROW        12 (i)
                    LIST_APPEND              2
                    JUMP_BACKWARD           31 (to L12)
           L15:     END_FOR
                    POP_ITER
           L16:     SWAP                     2
                    STORE_FAST              12 (i)
                    CALL                     1
    
    2496            BUILD_MAP                3
    
    2501            LOAD_CONST               3 ('anomalies')
    
    2502            LOAD_CONST              16 ('items')
                    LOAD_FAST_BORROW         3 (anomalies)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     13 (a)
                    SWAP                     2
           L17:     BUILD_LIST               0
                    SWAP                     2
           L18:     FOR_ITER                28 (to L21)
                    STORE_FAST_LOAD_FAST   221 (a, a)
                    LOAD_ATTR               27 (get + NULL|self)
                    LOAD_CONST              17 ('severity')
                    CALL                     1
                    LOAD_CONST              31 (('critical', 'high'))
                    CONTAINS_OP              0 (in)
           L19:     POP_JUMP_IF_TRUE         3 (to L20)
                    NOT_TAKEN
                    JUMP_BACKWARD           26 (to L18)
           L20:     LOAD_FAST_BORROW        13 (a)
                    LIST_APPEND              2
                    JUMP_BACKWARD           30 (to L18)
           L21:     END_FOR
                    POP_ITER
           L22:     SWAP                     2
                    STORE_FAST              13 (a)
    
    2503            LOAD_CONST              13 ('total')
                    LOAD_GLOBAL             25 (len + NULL)
                    LOAD_FAST_BORROW         3 (anomalies)
                    CALL                     1
    
    2501            BUILD_MAP                2
    
    2505            LOAD_CONST              18 ('today')
    
    2506            LOAD_CONST              19 ('events')
                    LOAD_GLOBAL             25 (len + NULL)
                    LOAD_FAST_BORROW         5 (today_events)
                    CALL                     1
    
    2507            LOAD_CONST              20 ('event_list')
    
    2511            LOAD_FAST_BORROW         5 (today_events)
                    LOAD_CONST              12 (slice(None, 5, None))
                    BINARY_OP               26 ([])
                    GET_ITER
    
    2507            LOAD_FAST_AND_CLEAR      7 (e)
                    SWAP                     2
           L23:     BUILD_LIST               0
                    SWAP                     2
    
    2511   L24:     FOR_ITER                32 (to L25)
                    STORE_FAST               7 (e)
    
    2508            LOAD_CONST              21 ('title')
                    LOAD_FAST_BORROW         7 (e)
                    LOAD_CONST              21 ('title')
                    BINARY_OP               26 ([])
    
    2509            LOAD_CONST              22 ('start')
                    LOAD_FAST_BORROW         7 (e)
                    LOAD_CONST               5 ('start_time')
                    BINARY_OP               26 ([])
    
    2510            LOAD_CONST              23 ('end')
                    LOAD_FAST_BORROW         7 (e)
                    LOAD_CONST               8 ('end_time')
                    BINARY_OP               26 ([])
    
    2507            BUILD_MAP                3
                    LIST_APPEND              2
                    JUMP_BACKWARD           34 (to L24)
    
    2511   L25:     END_FOR
                    POP_ITER
    
    2507   L26:     SWAP                     2
                    STORE_FAST               7 (e)
    
    2512            LOAD_CONST              24 ('total_event_hours')
                    LOAD_GLOBAL             29 (round + NULL)
                    LOAD_FAST_BORROW         6 (total_event_hours)
                    LOAD_SMALL_INT           1
                    CALL                     2
    
    2513            LOAD_CONST              25 ('available_hours')
                    LOAD_GLOBAL             29 (round + NULL)
                    LOAD_FAST_BORROW        11 (available)
                    LOAD_SMALL_INT           1
                    CALL                     2
    
    2514            LOAD_CONST              26 ('deep_work_hours')
                    LOAD_GLOBAL             29 (round + NULL)
                    LOAD_GLOBAL             23 (max + NULL)
                    LOAD_SMALL_INT           0
                    LOAD_FAST_BORROW        11 (available)
                    LOAD_SMALL_INT           2
                    BINARY_OP               10 (-)
                    CALL                     2
                    LOAD_SMALL_INT           1
                    CALL                     2
    
    2505            BUILD_MAP                5
    
    2516            LOAD_CONST              27 ('pending_approvals')
                    LOAD_GLOBAL              6 (store)
                    LOAD_ATTR               31 (count + NULL|self)
                    LOAD_CONST              28 ('decisions')
                    LOAD_CONST              29 ('approved IS NULL')
                    CALL                     2
    
    2517            LOAD_CONST              30 ('sync_status')
                    LOAD_GLOBAL             32 (collectors)
                    LOAD_ATTR               35 (get_status + NULL|self)
                    CALL                     0
    
    2495            BUILD_MAP                5
                    RETURN_VALUE
    
      --   L27:     PUSH_EXC_INFO
    
    2489            POP_TOP
    
    2490   L28:     POP_EXCEPT
                    EXTENDED_ARG             1
                    JUMP_BACKWARD          449 (to L6)
    
      --   L29:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L30:     SWAP                     2
                    POP_TOP
    
    2499            SWAP                     2
                    STORE_FAST              12 (i)
                    RERAISE                  0
    
      --   L31:     SWAP                     2
                    POP_TOP
    
    2502            SWAP                     2
                    STORE_FAST              13 (a)
                    RERAISE                  0
    
      --   L32:     SWAP                     2
                    POP_TOP
    
    2507            SWAP                     2
                    STORE_FAST               7 (e)
                    RERAISE                  0
    
      --   L33:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L33 [0] lasti
      L4 to L7 -> L33 [0] lasti
      L8 to L9 -> L27 [1]
      L9 to L11 -> L33 [0] lasti
      L11 to L13 -> L30 [10]
      L14 to L16 -> L30 [10]
      L16 to L17 -> L33 [0] lasti
      L17 to L19 -> L31 [6]
      L20 to L22 -> L31 [6]
      L22 to L23 -> L33 [0] lasti
      L23 to L26 -> L32 [10]
      L26 to L27 -> L33 [0] lasti
      L27 to L28 -> L29 [2] lasti
      L28 to L33 -> L33 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/search")
async def search_items(q, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2525
    
    2525           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    2528           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (query + NULL|self)
    
    2529           LOAD_CONST               1 ("SELECT * FROM tasks WHERE status = 'pending' AND title LIKE ? ORDER BY priority DESC LIMIT ?")
    
    2530           LOAD_CONST               2 ('%')
                   LOAD_FAST_BORROW         0 (q)
                   FORMAT_SIMPLE
                   LOAD_CONST               2 ('%')
                   BUILD_STRING             3
                   LOAD_FAST_BORROW         1 (limit)
                   BUILD_LIST               2
    
    2528           CALL                     2
                   STORE_FAST               2 (tasks)
    
    2533           LOAD_CONST               3 ('items')
    
    2540           LOAD_FAST_BORROW         2 (tasks)
                   GET_ITER
    
    2533           LOAD_FAST_AND_CLEAR      3 (t)
                   SWAP                     2
           L2:     BUILD_LIST               0
                   SWAP                     2
    
    2540   L3:     FOR_ITER                59 (to L4)
                   STORE_FAST               3 (t)
    
    2534           LOAD_CONST               4 ('id')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST               4 ('id')
                   BINARY_OP               26 ([])
    
    2535           LOAD_CONST               5 ('title')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST               5 ('title')
                   BINARY_OP               26 ([])
    
    2536           LOAD_CONST               6 ('score')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST               7 ('priority')
                   BINARY_OP               26 ([])
    
    2537           LOAD_CONST               8 ('due')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST               9 ('due_date')
                   BINARY_OP               26 ([])
    
    2538           LOAD_CONST              10 ('assignee')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST              10 ('assignee')
                   BINARY_OP               26 ([])
    
    2539           LOAD_CONST              11 ('source')
                   LOAD_FAST_BORROW         3 (t)
                   LOAD_CONST              11 ('source')
                   BINARY_OP               26 ([])
    
    2533           BUILD_MAP                6
                   LIST_APPEND              2
                   JUMP_BACKWARD           61 (to L3)
    
    2540   L4:     END_FOR
                   POP_ITER
    
    2533   L5:     SWAP                     2
                   STORE_FAST               3 (t)
    
    2541           LOAD_CONST              12 ('total')
                   LOAD_GLOBAL              5 (len + NULL)
                   LOAD_FAST_BORROW         2 (tasks)
                   CALL                     1
    
    2532           BUILD_MAP                2
                   RETURN_VALUE
    
      --   L6:     SWAP                     2
                   POP_TOP
    
    2533           SWAP                     2
                   STORE_FAST               3 (t)
                   RERAISE                  0
    
      --   L7:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L7 [0] lasti
      L2 to L5 -> L6 [3]
      L5 to L7 -> L7 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/team/workload")
async def get_team_workload():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2549
    
    2549            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2552            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT \n            assignee,\n            COUNT(*) as total,\n            SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue,\n            SUM(CASE WHEN due_date = date('now') THEN 1 ELSE 0 END) as due_today,\n            AVG(priority) as avg_priority\n        FROM tasks \n        WHERE status = 'pending' AND assignee IS NOT NULL AND assignee != ''\n        GROUP BY assignee\n        ORDER BY total DESC\n    ")
                    CALL                     1
                    STORE_FAST               0 (workload)
    
    2565            LOAD_CONST               2 ('team')
    
    2572            LOAD_FAST_BORROW         0 (workload)
                    GET_ITER
    
    2565            LOAD_FAST_AND_CLEAR      1 (w)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
    
    2572    L3:     FOR_ITER               124 (to L16)
                    STORE_FAST               1 (w)
    
    2566            LOAD_CONST               3 ('name')
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               4 ('assignee')
                    BINARY_OP               26 ([])
    
    2567            LOAD_CONST               5 ('total')
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               5 ('total')
                    BINARY_OP               26 ([])
    
    2568            LOAD_CONST               6 ('overdue')
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               6 ('overdue')
                    BINARY_OP               26 ([])
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L6)
            L4:     NOT_TAKEN
            L5:     POP_TOP
                    LOAD_SMALL_INT           0
    
    2569    L6:     LOAD_CONST               7 ('due_today')
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               7 ('due_today')
                    BINARY_OP               26 ([])
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L9)
            L7:     NOT_TAKEN
            L8:     POP_TOP
                    LOAD_SMALL_INT           0
    
    2570    L9:     LOAD_CONST               8 ('avg_priority')
                    LOAD_GLOBAL              5 (round + NULL)
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               8 ('avg_priority')
                    BINARY_OP               26 ([])
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L12)
           L10:     NOT_TAKEN
           L11:     POP_TOP
                    LOAD_SMALL_INT           0
           L12:     LOAD_SMALL_INT           1
                    CALL                     2
    
    2571            LOAD_CONST               9 ('status')
                    LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               5 ('total')
                    BINARY_OP               26 ([])
                    LOAD_SMALL_INT          15
                    COMPARE_OP             148 (bool(>))
                    POP_JUMP_IF_FALSE        3 (to L13)
                    NOT_TAKEN
                    LOAD_CONST              10 ('overloaded')
                    JUMP_FORWARD            17 (to L15)
           L13:     LOAD_FAST_BORROW         1 (w)
                    LOAD_CONST               5 ('total')
                    BINARY_OP               26 ([])
                    LOAD_SMALL_INT           8
                    COMPARE_OP             148 (bool(>))
                    POP_JUMP_IF_FALSE        3 (to L14)
                    NOT_TAKEN
                    LOAD_CONST              11 ('busy')
                    JUMP_FORWARD             1 (to L15)
           L14:     LOAD_CONST              12 ('available')
    
    2565   L15:     BUILD_MAP                6
                    LIST_APPEND              2
                    JUMP_BACKWARD          126 (to L3)
    
    2572   L16:     END_FOR
                    POP_ITER
    
    2565   L17:     SWAP                     2
                    STORE_FAST               1 (w)
    
    2564            BUILD_MAP                1
                    RETURN_VALUE
    
      --   L18:     SWAP                     2
                    POP_TOP
    
    2565            SWAP                     2
                    STORE_FAST               1 (w)
                    RERAISE                  0
    
      --   L19:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L19 [0] lasti
      L2 to L4 -> L18 [3]
      L5 to L7 -> L18 [3]
      L8 to L10 -> L18 [3]
      L11 to L17 -> L18 [3]
      L17 to L19 -> L19 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/priorities/grouped")
async def get_grouped_priorities(group_by, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2580
    
    2580            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2583            LOAD_FAST_BORROW         0 (group_by)
                    LOAD_CONST              14 (('project', 'assignee', 'source'))
                    CONTAINS_OP              1 (not in)
                    POP_JUMP_IF_FALSE        3 (to L2)
                    NOT_TAKEN
    
    2584            LOAD_CONST               1 ('project')
                    STORE_FAST               0 (group_by)
    
    2586    L2:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               2 ('\n        SELECT \n            ')
    
    2588            LOAD_FAST_BORROW         0 (group_by)
                    FORMAT_SIMPLE
                    LOAD_CONST               3 (" as group_name,\n            COUNT(*) as total,\n            SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue,\n            MAX(priority) as max_priority\n        FROM tasks \n        WHERE status = 'pending' AND ")
    
    2593            LOAD_FAST_BORROW         0 (group_by)
                    FORMAT_SIMPLE
                    LOAD_CONST               4 (' IS NOT NULL AND ')
                    LOAD_FAST_BORROW         0 (group_by)
                    FORMAT_SIMPLE
                    LOAD_CONST               5 (" != ''\n        GROUP BY ")
    
    2594            LOAD_FAST_BORROW         0 (group_by)
                    FORMAT_SIMPLE
                    LOAD_CONST               6 ('\n        ORDER BY overdue DESC, total DESC\n        LIMIT ?\n    ')
    
    2586            BUILD_STRING             9
    
    2597            LOAD_FAST_BORROW         1 (limit)
                    BUILD_LIST               1
    
    2586            CALL                     2
                    STORE_FAST               2 (groups)
    
    2600            LOAD_CONST               7 ('groups')
    
    2605            LOAD_FAST_BORROW         2 (groups)
                    GET_ITER
    
    2600            LOAD_FAST_AND_CLEAR      3 (g)
                    SWAP                     2
            L3:     BUILD_LIST               0
                    SWAP                     2
    
    2605    L4:     FOR_ITER                61 (to L11)
                    STORE_FAST               3 (g)
    
    2601            LOAD_CONST               8 ('name')
                    LOAD_FAST_BORROW         3 (g)
                    LOAD_CONST               9 ('group_name')
                    BINARY_OP               26 ([])
    
    2602            LOAD_CONST              10 ('total')
                    LOAD_FAST_BORROW         3 (g)
                    LOAD_CONST              10 ('total')
                    BINARY_OP               26 ([])
    
    2603            LOAD_CONST              11 ('overdue')
                    LOAD_FAST_BORROW         3 (g)
                    LOAD_CONST              11 ('overdue')
                    BINARY_OP               26 ([])
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L7)
            L5:     NOT_TAKEN
            L6:     POP_TOP
                    LOAD_SMALL_INT           0
    
    2604    L7:     LOAD_CONST              12 ('max_priority')
                    LOAD_FAST_BORROW         3 (g)
                    LOAD_CONST              12 ('max_priority')
                    BINARY_OP               26 ([])
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L10)
            L8:     NOT_TAKEN
            L9:     POP_TOP
                    LOAD_SMALL_INT           0
    
    2600   L10:     BUILD_MAP                4
                    LIST_APPEND              2
                    JUMP_BACKWARD           63 (to L4)
    
    2605   L11:     END_FOR
                    POP_ITER
    
    2600   L12:     SWAP                     2
                    STORE_FAST               3 (g)
    
    2606            LOAD_CONST              13 ('group_by')
                    LOAD_FAST_BORROW         0 (group_by)
    
    2599            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L13:     SWAP                     2
                    POP_TOP
    
    2600            SWAP                     2
                    STORE_FAST               3 (g)
                    RERAISE                  0
    
      --   L14:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L14 [0] lasti
      L3 to L5 -> L13 [3]
      L6 to L8 -> L13 [3]
      L9 to L12 -> L13 [3]
      L12 to L14 -> L14 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients")
async def get_clients(tier, health, ar_status, active_only, limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2614
    
    2614            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2631            LOAD_CONST               1 ('1=1')
                    BUILD_LIST               1
                    STORE_FAST               5 (conditions)
    
    2632            BUILD_LIST               0
                    STORE_FAST               6 (params)
    
    2634            LOAD_FAST_BORROW         0 (tier)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       35 (to L2)
                    NOT_TAKEN
    
    2635            LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               2 ('tier = ?')
                    CALL                     1
                    POP_TOP
    
    2636            LOAD_FAST_BORROW         6 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         0 (tier)
                    CALL                     1
                    POP_TOP
    
    2637    L2:     LOAD_FAST_BORROW         1 (health)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       35 (to L5)
            L3:     NOT_TAKEN
    
    2638    L4:     LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               3 ('relationship_health = ?')
                    CALL                     1
                    POP_TOP
    
    2639            LOAD_FAST_BORROW         6 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         1 (health)
                    CALL                     1
                    POP_TOP
    
    2640    L5:     LOAD_FAST_BORROW         2 (ar_status)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       75 (to L10)
            L6:     NOT_TAKEN
    
    2641    L7:     LOAD_FAST_BORROW         2 (ar_status)
                    LOAD_CONST               4 ('overdue')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       19 (to L8)
                    NOT_TAKEN
    
    2642            LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               5 ("financial_ar_outstanding > 0 AND financial_ar_aging IN ('30+', '60+', '90+')")
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD            49 (to L10)
    
    2643    L8:     LOAD_FAST_BORROW         2 (ar_status)
                    LOAD_CONST               6 ('any')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       19 (to L9)
                    NOT_TAKEN
    
    2644            LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               7 ('financial_ar_outstanding > 0')
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD            24 (to L10)
    
    2645    L9:     LOAD_FAST_BORROW         2 (ar_status)
                    LOAD_CONST               8 ('none')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       18 (to L10)
                    NOT_TAKEN
    
    2646            LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST               9 ('(financial_ar_outstanding IS NULL OR financial_ar_outstanding = 0)')
                    CALL                     1
                    POP_TOP
    
    2649   L10:     LOAD_FAST_BORROW         3 (active_only)
                    TO_BOOL
                    POP_JUMP_IF_FALSE      133 (to L22)
           L11:     NOT_TAKEN
    
    2650   L12:     LOAD_GLOBAL              2 (store)
                    LOAD_ATTR                5 (query + NULL|self)
                    LOAD_CONST              10 ("\n            SELECT DISTINCT client_id FROM tasks \n            WHERE client_id IS NOT NULL \n            AND (updated_at >= date('now', '-90 days') OR status = 'pending')\n            UNION\n            SELECT DISTINCT client_id FROM projects \n            WHERE client_id IS NOT NULL \n            AND enrollment_status = 'enrolled'\n        ")
                    CALL                     1
                    STORE_FAST               7 (active_client_ids)
    
    2659            LOAD_FAST_BORROW         7 (active_client_ids)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      8 (r)
                    SWAP                     2
           L13:     BUILD_LIST               0
                    SWAP                     2
           L14:     FOR_ITER                11 (to L15)
                    STORE_FAST_LOAD_FAST   136 (r, r)
                    LOAD_CONST              11 ('client_id')
                    BINARY_OP               26 ([])
                    LIST_APPEND              2
                    JUMP_BACKWARD           13 (to L14)
           L15:     END_FOR
                    POP_ITER
           L16:     STORE_FAST               9 (active_ids)
                    STORE_FAST               8 (r)
    
    2661            LOAD_FAST_BORROW         9 (active_ids)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       73 (to L21)
                    NOT_TAKEN
    
    2662            LOAD_CONST              12 (',')
                    LOAD_ATTR                7 (join + NULL|self)
                    LOAD_FAST_BORROW         9 (active_ids)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR     10 (_)
                    SWAP                     2
           L17:     BUILD_LIST               0
                    SWAP                     2
           L18:     FOR_ITER                 5 (to L19)
                    STORE_FAST              10 (_)
                    LOAD_CONST              13 ('?')
                    LIST_APPEND              2
                    JUMP_BACKWARD            7 (to L18)
           L19:     END_FOR
                    POP_ITER
           L20:     SWAP                     2
                    STORE_FAST              10 (_)
                    CALL                     1
                    STORE_FAST              11 (placeholders)
    
    2663            LOAD_FAST_BORROW         5 (conditions)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_CONST              14 ('id IN (')
                    LOAD_FAST_BORROW        11 (placeholders)
                    FORMAT_SIMPLE
                    LOAD_CONST              15 (')')
                    BUILD_STRING             3
                    CALL                     1
                    POP_TOP
    
    2664            LOAD_FAST_BORROW         6 (params)
                    LOAD_ATTR                9 (extend + NULL|self)
                    LOAD_FAST_BORROW         9 (active_ids)
                    CALL                     1
                    POP_TOP
                    JUMP_FORWARD             8 (to L22)
    
    2667   L21:     LOAD_CONST              16 ('items')
                    BUILD_LIST               0
                    LOAD_CONST              17 ('total')
                    LOAD_SMALL_INT           0
                    LOAD_CONST              18 ('active_only')
                    LOAD_CONST              19 (True)
                    BUILD_MAP                3
                    RETURN_VALUE
    
    2669   L22:     LOAD_FAST_BORROW         6 (params)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW         4 (limit)
                    CALL                     1
                    POP_TOP
    
    2671            LOAD_GLOBAL              2 (store)
                    LOAD_ATTR                5 (query + NULL|self)
                    LOAD_CONST              20 ('\n        SELECT * FROM clients \n        WHERE ')
    
    2673            LOAD_CONST              21 (' AND ')
                    LOAD_ATTR                7 (join + NULL|self)
                    LOAD_FAST_BORROW         5 (conditions)
                    CALL                     1
                    FORMAT_SIMPLE
                    LOAD_CONST              22 ("\n        ORDER BY \n            CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,\n            financial_ar_outstanding DESC NULLS LAST,\n            name\n        LIMIT ?\n    ")
    
    2671            BUILD_STRING             3
    
    2679            LOAD_FAST_BORROW         6 (params)
    
    2671            CALL                     2
                    STORE_FAST              12 (clients)
    
    2682            BUILD_LIST               0
                    STORE_FAST              13 (result)
    
    2683            LOAD_FAST_BORROW        12 (clients)
                    GET_ITER
           L23:     FOR_ITER               149 (to L30)
                    STORE_FAST              14 (c)
    
    2684            LOAD_GLOBAL             11 (dict + NULL)
                    LOAD_FAST_BORROW        14 (c)
                    CALL                     1
                    STORE_FAST              15 (client_dict)
    
    2687            LOAD_GLOBAL              2 (store)
                    LOAD_ATTR                5 (query + NULL|self)
    
    2688            LOAD_CONST              23 ("SELECT COUNT(*) as cnt FROM projects WHERE client_id = ? AND enrollment_status = 'enrolled'")
    
    2689            LOAD_FAST_BORROW        14 (c)
                    LOAD_CONST              24 ('id')
                    BINARY_OP               26 ([])
                    BUILD_LIST               1
    
    2687            CALL                     2
                    STORE_FAST              16 (projects)
    
    2691            LOAD_FAST_BORROW        16 (projects)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       17 (to L24)
                    NOT_TAKEN
                    LOAD_FAST_BORROW        16 (projects)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              25 ('cnt')
                    BINARY_OP               26 ([])
                    JUMP_FORWARD             1 (to L25)
           L24:     LOAD_SMALL_INT           0
           L25:     LOAD_FAST_BORROW        15 (client_dict)
                    LOAD_CONST              26 ('project_count')
                    STORE_SUBSCR
    
    2694            LOAD_GLOBAL              2 (store)
                    LOAD_ATTR                5 (query + NULL|self)
    
    2695            LOAD_CONST              27 ("SELECT COUNT(*) as cnt FROM tasks WHERE client_id = ? AND status = 'pending'")
    
    2696            LOAD_FAST_BORROW        14 (c)
                    LOAD_CONST              24 ('id')
                    BINARY_OP               26 ([])
                    BUILD_LIST               1
    
    2694            CALL                     2
                    STORE_FAST              17 (tasks)
    
    2698            LOAD_FAST_BORROW        17 (tasks)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       17 (to L28)
           L26:     NOT_TAKEN
           L27:     LOAD_FAST_BORROW        17 (tasks)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              25 ('cnt')
                    BINARY_OP               26 ([])
                    JUMP_FORWARD             1 (to L29)
           L28:     LOAD_SMALL_INT           0
           L29:     LOAD_FAST_BORROW        15 (client_dict)
                    LOAD_CONST              28 ('open_task_count')
                    STORE_SUBSCR
    
    2700            LOAD_FAST_BORROW        13 (result)
                    LOAD_ATTR                1 (append + NULL|self)
                    LOAD_FAST_BORROW        15 (client_dict)
                    CALL                     1
                    POP_TOP
                    JUMP_BACKWARD          151 (to L23)
    
    2683   L30:     END_FOR
                    POP_ITER
    
    2702            LOAD_CONST              16 ('items')
                    LOAD_FAST_BORROW        13 (result)
                    LOAD_CONST              17 ('total')
                    LOAD_GLOBAL             13 (len + NULL)
                    LOAD_FAST_BORROW        13 (result)
                    CALL                     1
                    LOAD_CONST              18 ('active_only')
                    LOAD_FAST_BORROW         3 (active_only)
                    BUILD_MAP                3
                    RETURN_VALUE
    
      --   L31:     SWAP                     2
                    POP_TOP
    
    2659            SWAP                     2
                    STORE_FAST               8 (r)
                    RERAISE                  0
    
      --   L32:     SWAP                     2
                    POP_TOP
    
    2662            SWAP                     2
                    STORE_FAST              10 (_)
                    RERAISE                  0
    
      --   L33:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L33 [0] lasti
      L4 to L6 -> L33 [0] lasti
      L7 to L11 -> L33 [0] lasti
      L12 to L13 -> L33 [0] lasti
      L13 to L16 -> L31 [2]
      L16 to L17 -> L33 [0] lasti
      L17 to L20 -> L32 [4]
      L20 to L26 -> L33 [0] lasti
      L27 to L33 -> L33 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/portfolio")
async def get_client_portfolio():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2705
    
    2705            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2709            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT \n            tier,\n            COUNT(*) as count,\n            SUM(financial_ar_outstanding) as total_ar,\n            SUM(CASE WHEN relationship_health IN ('poor', 'critical') THEN 1 ELSE 0 END) as at_risk\n        FROM clients\n        WHERE tier IS NOT NULL\n        GROUP BY tier\n        ORDER BY CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 END\n    ")
                    CALL                     1
                    STORE_FAST               0 (tier_stats)
    
    2722            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               2 ('\n        SELECT \n            relationship_health as health,\n            COUNT(*) as count\n        FROM clients\n        WHERE relationship_health IS NOT NULL\n        GROUP BY relationship_health\n    ')
                    CALL                     1
                    STORE_FAST               1 (health_stats)
    
    2732            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               3 ("\n        SELECT * FROM clients \n        WHERE (tier IN ('A', 'B') AND relationship_health IN ('poor', 'critical'))\n           OR (financial_ar_outstanding > 100000 AND financial_ar_aging = '90+')\n        ORDER BY tier, financial_ar_outstanding DESC\n        LIMIT 10\n    ")
                    CALL                     1
                    STORE_FAST               2 (at_risk)
    
    2741            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               4 ('\n        SELECT \n            COUNT(*) as total_clients,\n            SUM(financial_ar_outstanding) as total_ar,\n            SUM(financial_annual_value) as total_annual_value\n        FROM clients\n    ')
                    CALL                     1
                    STORE_FAST               3 (totals)
    
    2750            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               5 ("\n        SELECT \n            COUNT(*) as count,\n            COALESCE(SUM(financial_ar_outstanding), 0) as total\n        FROM clients\n        WHERE financial_ar_outstanding > 0 \n        AND financial_ar_aging IN ('30+', '60+', '90+')\n    ")
                    CALL                     1
                    STORE_FAST               4 (overdue_ar)
    
    2760            LOAD_CONST               6 ('by_tier')
                    LOAD_FAST_BORROW         0 (tier_stats)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (t)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                14 (to L4)
                    STORE_FAST               5 (t)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         5 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     SWAP                     2
                    STORE_FAST               5 (t)
    
    2761            LOAD_CONST               7 ('by_health')
                    LOAD_FAST_BORROW         1 (health_stats)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      6 (h)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                14 (to L8)
                    STORE_FAST               6 (h)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         6 (h)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L7)
            L8:     END_FOR
                    POP_ITER
            L9:     SWAP                     2
                    STORE_FAST               6 (h)
    
    2762            LOAD_CONST               8 ('at_risk')
                    LOAD_FAST_BORROW         2 (at_risk)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      7 (c)
                    SWAP                     2
           L10:     BUILD_LIST               0
                    SWAP                     2
           L11:     FOR_ITER                14 (to L12)
                    STORE_FAST               7 (c)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         7 (c)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L11)
           L12:     END_FOR
                    POP_ITER
           L13:     SWAP                     2
                    STORE_FAST               7 (c)
    
    2763            LOAD_CONST               9 ('totals')
                    LOAD_FAST_BORROW         3 (totals)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       19 (to L16)
           L14:     NOT_TAKEN
           L15:     LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         3 (totals)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    CALL                     1
                    JUMP_FORWARD             1 (to L17)
           L16:     BUILD_MAP                0
    
    2764   L17:     LOAD_CONST              10 ('overdue_ar')
                    LOAD_FAST_BORROW         4 (overdue_ar)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       20 (to L20)
           L18:     NOT_TAKEN
           L19:     LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         4 (overdue_ar)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    CALL                     1
    
    2759            BUILD_MAP                5
                    RETURN_VALUE
    
    2764   L20:     LOAD_CONST              11 ('count')
                    LOAD_SMALL_INT           0
                    LOAD_CONST              12 ('total')
                    LOAD_SMALL_INT           0
                    BUILD_MAP                2
    
    2759            BUILD_MAP                5
                    RETURN_VALUE
    
      --   L21:     SWAP                     2
                    POP_TOP
    
    2760            SWAP                     2
                    STORE_FAST               5 (t)
                    RERAISE                  0
    
      --   L22:     SWAP                     2
                    POP_TOP
    
    2761            SWAP                     2
                    STORE_FAST               6 (h)
                    RERAISE                  0
    
      --   L23:     SWAP                     2
                    POP_TOP
    
    2762            SWAP                     2
                    STORE_FAST               7 (c)
                    RERAISE                  0
    
      --   L24:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L24 [0] lasti
      L2 to L5 -> L21 [3]
      L5 to L6 -> L24 [0] lasti
      L6 to L9 -> L22 [5]
      L9 to L10 -> L24 [0] lasti
      L10 to L13 -> L23 [7]
      L13 to L14 -> L24 [0] lasti
      L15 to L18 -> L24 [0] lasti
      L19 to L24 -> L24 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/clients/{client_id}")
async def get_client_detail(client_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2768
    
    2768            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2771            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('clients')
                    LOAD_FAST_BORROW         0 (client_id)
                    CALL                     2
                    STORE_FAST               1 (client)
    
    2772            LOAD_FAST_BORROW         1 (client)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    2773            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Client not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    2776    L2:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                7 (query + NULL|self)
                    LOAD_CONST               4 ("\n        SELECT p.*,\n            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending') as open_tasks,\n            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending' AND t.due_date < date('now')) as overdue_tasks\n        FROM projects p\n        WHERE p.client_id = ? AND p.enrollment_status = 'enrolled'\n        ORDER BY p.involvement_type DESC, p.name\n    ")
    
    2783            LOAD_FAST_BORROW         0 (client_id)
                    BUILD_LIST               1
    
    2776            CALL                     2
                    STORE_FAST               2 (all_projects)
    
    2786            LOAD_FAST_BORROW         2 (all_projects)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      3 (p)
                    SWAP                     2
            L3:     BUILD_LIST               0
                    SWAP                     2
            L4:     FOR_ITER                29 (to L7)
                    STORE_FAST_LOAD_FAST    51 (p, p)
                    LOAD_CONST               5 ('involvement_type')
                    BINARY_OP               26 ([])
                    LOAD_CONST               6 ('retainer')
                    COMPARE_OP              88 (bool(==))
            L5:     POP_JUMP_IF_TRUE         3 (to L6)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L4)
            L6:     LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         3 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           31 (to L4)
            L7:     END_FOR
                    POP_ITER
            L8:     STORE_FAST               4 (retainers)
                    STORE_FAST               3 (p)
    
    2787            LOAD_FAST_BORROW         2 (all_projects)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      3 (p)
                    SWAP                     2
            L9:     BUILD_LIST               0
                    SWAP                     2
           L10:     FOR_ITER                29 (to L13)
                    STORE_FAST_LOAD_FAST    51 (p, p)
                    LOAD_CONST               5 ('involvement_type')
                    BINARY_OP               26 ([])
                    LOAD_CONST               7 ('project')
                    COMPARE_OP              88 (bool(==))
           L11:     POP_JUMP_IF_TRUE         3 (to L12)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L10)
           L12:     LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         3 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           31 (to L10)
           L13:     END_FOR
                    POP_ITER
           L14:     STORE_FAST               5 (projects)
                    STORE_FAST               3 (p)
    
    2790            LOAD_GLOBAL             11 (sum + NULL)
                    LOAD_CONST               8 (<code object <genexpr> at 0x1009ed350, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 2790>)
                    MAKE_FUNCTION
                    LOAD_FAST_BORROW         2 (all_projects)
                    GET_ITER
                    CALL                     0
                    CALL                     1
                    STORE_FAST               6 (total_tasks)
    
    2791            LOAD_GLOBAL             11 (sum + NULL)
                    LOAD_CONST               9 (<code object <genexpr> at 0x1009ed470, file "/Users/molhamhomsi/clawd/moh_time_os/api/server.py", line 2791>)
                    MAKE_FUNCTION
                    LOAD_FAST_BORROW         2 (all_projects)
                    GET_ITER
                    CALL                     0
                    CALL                     1
                    STORE_FAST               7 (total_overdue)
    
    2794            LOAD_FAST_BORROW         1 (client)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              10 ('financial_ar_outstanding')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L15)
                    NOT_TAKEN
                    POP_TOP
                    LOAD_SMALL_INT           0
           L15:     STORE_FAST               8 (ar_outstanding)
    
    2795            LOAD_FAST_BORROW         1 (client)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              11 ('financial_ar_aging')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L18)
           L16:     NOT_TAKEN
           L17:     POP_TOP
                    LOAD_CONST              12 ('current')
           L18:     STORE_FAST               9 (ar_aging)
    
    2796            LOAD_FAST_BORROW         1 (client)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              13 ('financial_annual_value')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L21)
           L19:     NOT_TAKEN
           L20:     POP_TOP
                    LOAD_SMALL_INT           0
           L21:     STORE_FAST              10 (annual_value)
    
    2799            BUILD_LIST               0
                    STORE_FAST              11 (contacts)
    
    2800            LOAD_FAST_BORROW         1 (client)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST              14 ('contacts_json')
                    CALL                     1
                    TO_BOOL
                    POP_JUMP_IF_FALSE       31 (to L24)
           L22:     NOT_TAKEN
    
    2801            NOP
    
    2802   L23:     LOAD_GLOBAL             12 (json)
                    LOAD_ATTR               14 (loads)
                    PUSH_NULL
                    LOAD_FAST_BORROW         1 (client)
                    LOAD_CONST              14 ('contacts_json')
                    BINARY_OP               26 ([])
                    CALL                     1
                    STORE_FAST              11 (contacts)
    
    2807   L24:     LOAD_CONST              15 ('client')
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         1 (client)
                    CALL                     1
    
    2808            LOAD_CONST              16 ('retainers')
                    LOAD_FAST_BORROW         4 (retainers)
    
    2809            LOAD_CONST              17 ('projects')
                    LOAD_FAST_BORROW         5 (projects)
    
    2810            LOAD_CONST              18 ('summary')
    
    2811            LOAD_CONST              19 ('total_tasks')
                    LOAD_FAST_BORROW         6 (total_tasks)
    
    2812            LOAD_CONST              20 ('overdue_tasks')
                    LOAD_FAST_BORROW         7 (total_overdue)
    
    2813            LOAD_CONST              21 ('retainer_count')
                    LOAD_GLOBAL             17 (len + NULL)
                    LOAD_FAST_BORROW         4 (retainers)
                    CALL                     1
    
    2814            LOAD_CONST              22 ('project_count')
                    LOAD_GLOBAL             17 (len + NULL)
                    LOAD_FAST_BORROW         5 (projects)
                    CALL                     1
    
    2815            LOAD_CONST              23 ('ar_outstanding')
                    LOAD_FAST_BORROW         8 (ar_outstanding)
    
    2816            LOAD_CONST              24 ('ar_aging')
                    LOAD_FAST_BORROW         9 (ar_aging)
    
    2817            LOAD_CONST              25 ('annual_value')
                    LOAD_FAST_BORROW        10 (annual_value)
    
    2810            BUILD_MAP                7
    
    2819            LOAD_CONST              26 ('contacts')
                    LOAD_FAST_BORROW        11 (contacts)
    
    2806            BUILD_MAP                5
                    RETURN_VALUE
    
      --   L25:     SWAP                     2
                    POP_TOP
    
    2786            SWAP                     2
                    STORE_FAST               3 (p)
                    RERAISE                  0
    
      --   L26:     SWAP                     2
                    POP_TOP
    
    2787            SWAP                     2
                    STORE_FAST               3 (p)
                    RERAISE                  0
    
      --   L27:     PUSH_EXC_INFO
    
    2803            POP_TOP
    
    2804   L28:     POP_EXCEPT
                    JUMP_BACKWARD_NO_INTERRUPT 67 (to L24)
    
      --   L29:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L30:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L30 [0] lasti
      L3 to L5 -> L25 [2]
      L6 to L8 -> L25 [2]
      L8 to L9 -> L30 [0] lasti
      L9 to L11 -> L26 [2]
      L12 to L14 -> L26 [2]
      L14 to L16 -> L30 [0] lasti
      L17 to L19 -> L30 [0] lasti
      L20 to L22 -> L30 [0] lasti
      L23 to L24 -> L27 [0]
      L24 to L27 -> L30 [0] lasti
      L27 to L28 -> L29 [1] lasti
      L28 to L30 -> L30 [0] lasti
    """
    raise NotImplementedError

@app.put("/api/clients/{client_id}")
async def update_client(client_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2831
    
    2831            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2834            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('clients')
                    LOAD_FAST_BORROW         0 (client_id)
                    CALL                     2
                    STORE_FAST               2 (client)
    
    2835            LOAD_FAST_BORROW         2 (client)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    2836            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Client not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    2838    L2:     BUILD_MAP                0
                    STORE_FAST               3 (updates)
    
    2839            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                6 (tier)
                    POP_JUMP_IF_NONE        55 (to L7)
                    NOT_TAKEN
    
    2840            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                6 (tier)
                    LOAD_CONST              17 (('A', 'B', 'C', ''))
                    CONTAINS_OP              1 (not in)
                    POP_JUMP_IF_FALSE       13 (to L3)
                    NOT_TAKEN
    
    2841            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               5 (400)
                    LOAD_CONST               6 ('Tier must be A, B, or C')
                    CALL                     2
                    RAISE_VARARGS            1
    
    2842    L3:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                6 (tier)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L6)
            L4:     NOT_TAKEN
            L5:     POP_TOP
                    LOAD_CONST               4 (None)
            L6:     LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST               7 ('tier')
                    STORE_SUBSCR
    
    2843    L7:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                8 (health)
                    POP_JUMP_IF_NONE        26 (to L11)
                    NOT_TAKEN
    
    2844            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                8 (health)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L10)
            L8:     NOT_TAKEN
            L9:     POP_TOP
                    LOAD_CONST               4 (None)
           L10:     LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST               8 ('relationship_health')
                    STORE_SUBSCR
    
    2845   L11:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               10 (trend)
                    POP_JUMP_IF_NONE        26 (to L15)
                    NOT_TAKEN
    
    2846            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               10 (trend)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L14)
           L12:     NOT_TAKEN
           L13:     POP_TOP
                    LOAD_CONST               4 (None)
           L14:     LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST               9 ('relationship_trend')
                    STORE_SUBSCR
    
    2847   L15:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (notes)
                    POP_JUMP_IF_NONE        16 (to L16)
                    NOT_TAKEN
    
    2848            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (notes)
                    LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST              10 ('relationship_notes')
                    STORE_SUBSCR
    
    2849   L16:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               14 (annual_value)
                    POP_JUMP_IF_NONE        16 (to L17)
                    NOT_TAKEN
    
    2850            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               14 (annual_value)
                    LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST              11 ('financial_annual_value')
                    STORE_SUBSCR
    
    2852   L17:     LOAD_FAST_BORROW         3 (updates)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       61 (to L20)
           L18:     NOT_TAKEN
    
    2853   L19:     LOAD_GLOBAL             16 (datetime)
                    LOAD_ATTR               18 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               21 (isoformat + NULL|self)
                    CALL                     0
                    LOAD_FAST_BORROW         3 (updates)
                    LOAD_CONST              12 ('updated_at')
                    STORE_SUBSCR
    
    2854            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               23 (update + NULL|self)
                    LOAD_CONST               1 ('clients')
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 3 (client_id, updates)
                    CALL                     3
                    POP_TOP
    
    2856   L20:     LOAD_CONST              13 ('success')
                    LOAD_CONST              14 (True)
                    LOAD_CONST              15 ('id')
                    LOAD_FAST_BORROW         0 (client_id)
                    LOAD_CONST              16 ('updated')
                    LOAD_GLOBAL             25 (list + NULL)
                    LOAD_FAST_BORROW         3 (updates)
                    LOAD_ATTR               27 (keys + NULL|self)
                    CALL                     0
                    CALL                     1
                    BUILD_MAP                3
                    RETURN_VALUE
    
      --   L21:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L21 [0] lasti
      L5 to L8 -> L21 [0] lasti
      L9 to L12 -> L21 [0] lasti
      L13 to L18 -> L21 [0] lasti
      L19 to L21 -> L21 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/projects/candidates")
async def get_project_candidates():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2896
    
    2896            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2899            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT p.*, c.name as client_name\n        FROM projects p\n        LEFT JOIN clients c ON p.client_id = c.id\n        WHERE p.enrollment_status IN ('candidate', 'proposed')\n        ORDER BY p.proposed_at DESC NULLS LAST, p.name\n    ")
                    CALL                     1
                    STORE_FAST               0 (candidates)
    
    2908            LOAD_CONST               2 ('items')
                    LOAD_FAST_BORROW         0 (candidates)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      1 (p)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                14 (to L4)
                    STORE_FAST               1 (p)
                    LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         1 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L3)
            L4:     END_FOR
                    POP_ITER
            L5:     SWAP                     2
                    STORE_FAST               1 (p)
    
    2909            LOAD_CONST               3 ('total')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         0 (candidates)
                    CALL                     1
    
    2910            LOAD_CONST               4 ('proposed')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         0 (candidates)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      1 (p)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
            L7:     FOR_ITER                20 (to L10)
                    STORE_FAST_LOAD_FAST    17 (p, p)
                    LOAD_CONST               5 ('enrollment_status')
                    BINARY_OP               26 ([])
                    LOAD_CONST               4 ('proposed')
                    COMPARE_OP              88 (bool(==))
            L8:     POP_JUMP_IF_TRUE         3 (to L9)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L7)
            L9:     LOAD_FAST_BORROW         1 (p)
                    LIST_APPEND              2
                    JUMP_BACKWARD           22 (to L7)
           L10:     END_FOR
                    POP_ITER
           L11:     SWAP                     2
                    STORE_FAST               1 (p)
                    CALL                     1
    
    2911            LOAD_CONST               6 ('candidates')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         0 (candidates)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      1 (p)
                    SWAP                     2
           L12:     BUILD_LIST               0
                    SWAP                     2
           L13:     FOR_ITER                20 (to L16)
                    STORE_FAST_LOAD_FAST    17 (p, p)
                    LOAD_CONST               5 ('enrollment_status')
                    BINARY_OP               26 ([])
                    LOAD_CONST               7 ('candidate')
                    COMPARE_OP              88 (bool(==))
           L14:     POP_JUMP_IF_TRUE         3 (to L15)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L13)
           L15:     LOAD_FAST_BORROW         1 (p)
                    LIST_APPEND              2
                    JUMP_BACKWARD           22 (to L13)
           L16:     END_FOR
                    POP_ITER
           L17:     SWAP                     2
                    STORE_FAST               1 (p)
                    CALL                     1
    
    2907            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L18:     SWAP                     2
                    POP_TOP
    
    2908            SWAP                     2
                    STORE_FAST               1 (p)
                    RERAISE                  0
    
      --   L19:     SWAP                     2
                    POP_TOP
    
    2910            SWAP                     2
                    STORE_FAST               1 (p)
                    RERAISE                  0
    
      --   L20:     SWAP                     2
                    POP_TOP
    
    2911            SWAP                     2
                    STORE_FAST               1 (p)
                    RERAISE                  0
    
      --   L21:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L21 [0] lasti
      L2 to L5 -> L18 [3]
      L5 to L6 -> L21 [0] lasti
      L6 to L8 -> L19 [9]
      L9 to L11 -> L19 [9]
      L11 to L12 -> L21 [0] lasti
      L12 to L14 -> L20 [11]
      L15 to L17 -> L20 [11]
      L17 to L21 -> L21 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/projects/enrolled")
async def get_enrolled_projects():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2915
    
    2915            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2918            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT p.*, c.name as client_name, c.tier as client_tier,\n            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending') as open_tasks,\n            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending' AND t.due_date < date('now')) as overdue_tasks\n        FROM projects p\n        LEFT JOIN clients c ON p.client_id = c.id\n        WHERE p.enrollment_status = 'enrolled'\n        ORDER BY p.involvement_type DESC, c.tier NULLS LAST, p.name\n    ")
                    CALL                     1
                    STORE_FAST               0 (projects)
    
    2929            LOAD_FAST_BORROW         0 (projects)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      1 (p)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
            L3:     FOR_ITER                29 (to L6)
                    STORE_FAST_LOAD_FAST    17 (p, p)
                    LOAD_CONST               2 ('involvement_type')
                    BINARY_OP               26 ([])
                    LOAD_CONST               3 ('retainer')
                    COMPARE_OP              88 (bool(==))
            L4:     POP_JUMP_IF_TRUE         3 (to L5)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L3)
            L5:     LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         1 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           31 (to L3)
            L6:     END_FOR
                    POP_ITER
            L7:     STORE_FAST               2 (retainers)
                    STORE_FAST               1 (p)
    
    2930            LOAD_FAST_BORROW         0 (projects)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      1 (p)
                    SWAP                     2
            L8:     BUILD_LIST               0
                    SWAP                     2
            L9:     FOR_ITER                29 (to L12)
                    STORE_FAST_LOAD_FAST    17 (p, p)
                    LOAD_CONST               2 ('involvement_type')
                    BINARY_OP               26 ([])
                    LOAD_CONST               4 ('project')
                    COMPARE_OP              88 (bool(==))
           L10:     POP_JUMP_IF_TRUE         3 (to L11)
                    NOT_TAKEN
                    JUMP_BACKWARD           18 (to L9)
           L11:     LOAD_GLOBAL              5 (dict + NULL)
                    LOAD_FAST_BORROW         1 (p)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           31 (to L9)
           L12:     END_FOR
                    POP_ITER
           L13:     STORE_FAST               3 (active_projects)
                    STORE_FAST               1 (p)
    
    2933            LOAD_CONST               5 ('retainers')
                    LOAD_FAST_BORROW         2 (retainers)
    
    2934            LOAD_CONST               6 ('projects')
                    LOAD_FAST_BORROW         3 (active_projects)
    
    2935            LOAD_CONST               7 ('total_retainers')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         2 (retainers)
                    CALL                     1
    
    2936            LOAD_CONST               8 ('total_projects')
                    LOAD_GLOBAL              7 (len + NULL)
                    LOAD_FAST_BORROW         3 (active_projects)
                    CALL                     1
    
    2932            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L14:     SWAP                     2
                    POP_TOP
    
    2929            SWAP                     2
                    STORE_FAST               1 (p)
                    RERAISE                  0
    
      --   L15:     SWAP                     2
                    POP_TOP
    
    2930            SWAP                     2
                    STORE_FAST               1 (p)
                    RERAISE                  0
    
      --   L16:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L16 [0] lasti
      L2 to L4 -> L14 [2]
      L5 to L7 -> L14 [2]
      L7 to L8 -> L16 [0] lasti
      L8 to L10 -> L15 [2]
      L11 to L13 -> L15 [2]
      L13 to L16 -> L16 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/projects/{project_id}/enrollment")
async def process_enrollment(project_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2948
    
    2948            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    2951            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW         0 (project_id)
                    CALL                     2
                    STORE_FAST               2 (project)
    
    2952            LOAD_FAST_BORROW         2 (project)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    2953            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Project not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    2955    L2:     LOAD_GLOBAL              6 (datetime)
                    LOAD_ATTR                8 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               11 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               3 (now)
    
    2957            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST               4 ('enroll')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE      105 (to L9)
                    NOT_TAKEN
    
    2959            LOAD_CONST               5 ('enrollment_status')
                    LOAD_CONST               6 ('enrolled')
    
    2960            LOAD_CONST               7 ('enrolled_at')
                    LOAD_FAST_BORROW         3 (now)
    
    2961            LOAD_CONST               8 ('updated_at')
                    LOAD_FAST_BORROW         3 (now)
    
    2958            BUILD_MAP                3
                    STORE_FAST               4 (updates)
    
    2963            LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               14 (client_id)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       16 (to L5)
            L3:     NOT_TAKEN
    
    2964    L4:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               14 (client_id)
                    LOAD_FAST_BORROW         4 (updates)
                    LOAD_CONST               9 ('client_id')
                    STORE_SUBSCR
    
    2965    L5:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               16 (involvement_type)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       16 (to L8)
            L6:     NOT_TAKEN
    
    2966    L7:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               16 (involvement_type)
                    LOAD_FAST_BORROW         4 (updates)
                    LOAD_CONST              10 ('involvement_type')
                    STORE_SUBSCR
    
    2968    L8:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               19 (update + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW_LOAD_FAST_BORROW 4 (project_id, updates)
                    CALL                     3
                    POP_TOP
    
    2969            LOAD_CONST              11 ('success')
                    LOAD_CONST              12 (True)
                    LOAD_CONST              13 ('status')
                    LOAD_CONST               6 ('enrolled')
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (project_id)
                    BUILD_MAP                3
                    RETURN_VALUE
    
    2971    L9:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST              15 ('reject')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       36 (to L10)
                    NOT_TAKEN
    
    2972            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               19 (update + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW         0 (project_id)
    
    2973            LOAD_CONST               5 ('enrollment_status')
                    LOAD_CONST              16 ('rejected')
    
    2974            LOAD_CONST               8 ('updated_at')
                    LOAD_FAST_BORROW         3 (now)
    
    2972            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    2976            LOAD_CONST              11 ('success')
                    LOAD_CONST              12 (True)
                    LOAD_CONST              13 ('status')
                    LOAD_CONST              16 ('rejected')
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (project_id)
                    BUILD_MAP                3
                    RETURN_VALUE
    
    2978   L10:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST              17 ('snooze')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE      113 (to L14)
                    NOT_TAKEN
    
    2979            LOAD_SMALL_INT           0
                    LOAD_CONST              18 (('timedelta',))
                    IMPORT_NAME              3 (datetime)
                    IMPORT_FROM             10 (timedelta)
                    STORE_FAST               5 (timedelta)
                    POP_TOP
    
    2980            LOAD_GLOBAL              6 (datetime)
                    LOAD_ATTR                8 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_FAST                5 (timedelta)
                    PUSH_NULL
                    LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               22 (snooze_days)
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L13)
           L11:     NOT_TAKEN
           L12:     POP_TOP
                    LOAD_SMALL_INT          14
           L13:     LOAD_CONST              19 (('days',))
                    CALL_KW                  1
                    BINARY_OP                0 (+)
                    LOAD_ATTR               11 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               6 (snooze_until)
    
    2981            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               19 (update + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW         0 (project_id)
    
    2982            LOAD_CONST               5 ('enrollment_status')
                    LOAD_CONST              20 ('snoozed')
    
    2983            LOAD_CONST               8 ('updated_at')
                    LOAD_FAST_BORROW         3 (now)
    
    2981            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    2986            LOAD_CONST              11 ('success')
                    LOAD_CONST              12 (True)
                    LOAD_CONST              13 ('status')
                    LOAD_CONST              20 ('snoozed')
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (project_id)
                    LOAD_CONST              21 ('until')
                    LOAD_FAST_BORROW         6 (snooze_until)
                    BUILD_MAP                4
                    RETURN_VALUE
    
    2988   L14:     LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (action)
                    LOAD_CONST              22 ('internal')
                    COMPARE_OP              88 (bool(==))
                    POP_JUMP_IF_FALSE       36 (to L15)
                    NOT_TAKEN
    
    2989            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               19 (update + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW         0 (project_id)
    
    2990            LOAD_CONST               5 ('enrollment_status')
                    LOAD_CONST              22 ('internal')
    
    2991            LOAD_CONST               8 ('updated_at')
                    LOAD_FAST_BORROW         3 (now)
    
    2989            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    2993            LOAD_CONST              11 ('success')
                    LOAD_CONST              12 (True)
                    LOAD_CONST              13 ('status')
                    LOAD_CONST              22 ('internal')
                    LOAD_CONST              14 ('id')
                    LOAD_FAST_BORROW         0 (project_id)
                    BUILD_MAP                3
                    RETURN_VALUE
    
    2996   L15:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST              23 (400)
                    LOAD_CONST              24 ('Unknown action: ')
                    LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR               12 (action)
                    FORMAT_SIMPLE
                    BUILD_STRING             2
                    CALL                     2
                    RAISE_VARARGS            1
    
      --   L16:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L16 [0] lasti
      L4 to L6 -> L16 [0] lasti
      L7 to L11 -> L16 [0] lasti
      L12 to L16 -> L16 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/projects/detect")
async def detect_new_projects(test_mode):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:2999
    
    2999           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3007           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('run_detection',))
                   IMPORT_NAME              0 (lib.enrollment_detector)
                   IMPORT_FROM              1 (run_detection)
                   STORE_FAST               1 (run_detection)
                   POP_TOP
    
    3008           LOAD_FAST_BORROW         1 (run_detection)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   LOAD_FAST_BORROW         0 (test_mode)
                   LOAD_CONST               2 (('test_mode',))
                   CALL_KW                  2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/projects/{project_id}")
async def get_project_detail(project_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3011
    
    3011            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3014            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('projects')
                    LOAD_FAST_BORROW         0 (project_id)
                    CALL                     2
                    STORE_FAST               1 (project)
    
    3015            LOAD_FAST_BORROW         1 (project)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    3016            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Project not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    3019    L2:     LOAD_CONST               4 (None)
                    STORE_FAST               2 (client)
    
    3020            LOAD_FAST_BORROW         1 (project)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               5 ('client_id')
                    CALL                     1
                    TO_BOOL
                    POP_JUMP_IF_FALSE       30 (to L5)
            L3:     NOT_TAKEN
    
    3021    L4:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               6 ('clients')
                    LOAD_FAST_BORROW         1 (project)
                    LOAD_CONST               5 ('client_id')
                    BINARY_OP               26 ([])
                    CALL                     2
                    STORE_FAST               2 (client)
    
    3024    L5:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                7 (query + NULL|self)
                    LOAD_CONST               7 ("\n        SELECT * FROM tasks \n        WHERE project = ? AND status = 'pending'\n        ORDER BY due_date ASC NULLS LAST, priority DESC\n        LIMIT 30\n    ")
    
    3029            LOAD_FAST_BORROW         1 (project)
                    LOAD_CONST               8 ('name')
                    BINARY_OP               26 ([])
                    BUILD_LIST               1
    
    3024            CALL                     2
                    STORE_FAST               3 (tasks)
    
    3032            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                7 (query + NULL|self)
                    LOAD_CONST               9 ("\n        SELECT COUNT(*) as cnt FROM tasks \n        WHERE project = ? AND status = 'pending' AND due_date < date('now')\n    ")
    
    3035            LOAD_FAST_BORROW         1 (project)
                    LOAD_CONST               8 ('name')
                    BINARY_OP               26 ([])
                    BUILD_LIST               1
    
    3032            CALL                     2
                    STORE_FAST               4 (overdue)
    
    3038            LOAD_CONST              10 ('project')
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         1 (project)
                    CALL                     1
    
    3039            LOAD_CONST              11 ('client')
                    LOAD_FAST_BORROW         2 (client)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       12 (to L6)
                    NOT_TAKEN
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         2 (client)
                    CALL                     1
                    JUMP_FORWARD             1 (to L7)
            L6:     LOAD_CONST               4 (None)
    
    3040    L7:     LOAD_CONST              12 ('tasks')
                    LOAD_FAST_BORROW         3 (tasks)
                    GET_ITER
                    LOAD_FAST_AND_CLEAR      5 (t)
                    SWAP                     2
            L8:     BUILD_LIST               0
                    SWAP                     2
            L9:     FOR_ITER                14 (to L10)
                    STORE_FAST               5 (t)
                    LOAD_GLOBAL              9 (dict + NULL)
                    LOAD_FAST_BORROW         5 (t)
                    CALL                     1
                    LIST_APPEND              2
                    JUMP_BACKWARD           16 (to L9)
           L10:     END_FOR
                    POP_ITER
           L11:     SWAP                     2
                    STORE_FAST               5 (t)
    
    3041            LOAD_CONST              13 ('overdue_count')
                    LOAD_FAST_BORROW         4 (overdue)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       18 (to L14)
           L12:     NOT_TAKEN
           L13:     LOAD_FAST_BORROW         4 (overdue)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              14 ('cnt')
                    BINARY_OP               26 ([])
    
    3037            BUILD_MAP                4
                    RETURN_VALUE
    
    3041   L14:     LOAD_SMALL_INT           0
    
    3037            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L15:     SWAP                     2
                    POP_TOP
    
    3040            SWAP                     2
                    STORE_FAST               5 (t)
                    RERAISE                  0
    
      --   L16:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L16 [0] lasti
      L4 to L8 -> L16 [0] lasti
      L8 to L11 -> L15 [7]
      L11 to L12 -> L16 [0] lasti
      L13 to L16 -> L16 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/sync/xero")
async def sync_xero():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3045
    
    3045           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3048           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('sync',))
                   IMPORT_NAME              0 (lib.collectors.xero)
                   IMPORT_FROM              1 (sync)
                   STORE_FAST               0 (sync)
                   POP_TOP
    
    3049           LOAD_FAST_BORROW         0 (sync)
                   PUSH_NULL
                   CALL                     0
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/link")
async def bulk_link_tasks():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3052
    
    3052           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3055           LOAD_SMALL_INT           0
                   LOAD_CONST               1 (('bulk_link_tasks',))
                   IMPORT_NAME              0 (lib.task_parser)
                   IMPORT_FROM              1 (bulk_link_tasks)
                   STORE_FAST               0 (bulk_link_tasks)
                   POP_TOP
    
    3056           LOAD_FAST_BORROW         0 (bulk_link_tasks)
                   PUSH_NULL
                   LOAD_GLOBAL              4 (store)
                   CALL                     1
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/projects/propose")
async def propose_project(name, project_type):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3059
    
    3059           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3062           LOAD_GLOBAL              0 (datetime)
                   LOAD_ATTR                2 (now)
                   PUSH_NULL
                   CALL                     0
                   LOAD_ATTR                5 (isoformat + NULL|self)
                   CALL                     0
                   STORE_FAST               2 (now)
    
    3063           LOAD_CONST               1 ('prop-')
                   LOAD_FAST_BORROW         0 (name)
                   LOAD_ATTR                7 (lower + NULL|self)
                   CALL                     0
                   LOAD_ATTR                9 (replace + NULL|self)
                   LOAD_CONST               2 (' ')
                   LOAD_CONST               3 ('-')
                   CALL                     2
                   LOAD_CONST               4 (slice(None, 20, None))
                   BINARY_OP               26 ([])
                   FORMAT_SIMPLE
                   BUILD_STRING             2
                   STORE_FAST               3 (project_id)
    
    3065           LOAD_GLOBAL             10 (store)
                   LOAD_ATTR               13 (upsert + NULL|self)
                   LOAD_CONST               5 ('projects')
    
    3066           LOAD_CONST               6 ('id')
                   LOAD_FAST                3 (project_id)
    
    3067           LOAD_CONST               7 ('name')
                   LOAD_FAST_BORROW         1 (project_type)
                   LOAD_CONST               8 ('retainer')
                   COMPARE_OP              88 (bool(==))
                   POP_JUMP_IF_FALSE        6 (to L2)
                   NOT_TAKEN
                   LOAD_FAST_BORROW         0 (name)
                   FORMAT_SIMPLE
                   LOAD_CONST               9 (' Monthly')
                   BUILD_STRING             2
                   JUMP_FORWARD             1 (to L3)
           L2:     LOAD_FAST                0 (name)
    
    3068   L3:     LOAD_CONST              10 ('enrollment_status')
                   LOAD_CONST              11 ('proposed')
    
    3069           LOAD_CONST              12 ('involvement_type')
                   LOAD_FAST_BORROW         1 (project_type)
    
    3070           LOAD_CONST              13 ('proposed_at')
                   LOAD_FAST_BORROW         2 (now)
    
    3071           LOAD_CONST              14 ('created_at')
                   LOAD_FAST_BORROW         2 (now)
    
    3072           LOAD_CONST              15 ('updated_at')
                   LOAD_FAST_BORROW         2 (now)
    
    3065           BUILD_MAP                7
                   CALL                     2
                   POP_TOP
    
    3075           LOAD_CONST              16 ('success')
                   LOAD_CONST              17 (True)
                   LOAD_CONST               6 ('id')
                   LOAD_FAST_BORROW         3 (project_id)
                   LOAD_CONST              18 ('status')
                   LOAD_CONST              11 ('proposed')
                   BUILD_MAP                3
                   RETURN_VALUE
    
      --   L4:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L4 -> L4 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/emails")
async def get_email_queue(limit):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3082
    
    3082            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3085            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ('\n        SELECT * FROM communications \n        WHERE (processed = 0 OR processed IS NULL)\n        ORDER BY received_at DESC\n        LIMIT ?\n    ')
    
    3090            LOAD_FAST_BORROW         0 (limit)
                    BUILD_LIST               1
    
    3085            CALL                     2
                    STORE_FAST               1 (emails)
    
    3093            LOAD_CONST               2 ('items')
    
    3100            LOAD_FAST_BORROW         1 (emails)
                    GET_ITER
    
    3093            LOAD_FAST_AND_CLEAR      2 (e)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
    
    3100    L3:     FOR_ITER               236 (to L22)
                    STORE_FAST               2 (e)
    
    3094            LOAD_CONST               3 ('id')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_CONST               3 ('id')
                    BINARY_OP               26 ([])
    
    3095            LOAD_CONST               4 ('subject')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST               4 ('subject')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        28 (to L8)
            L4:     NOT_TAKEN
            L5:     POP_TOP
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST               5 ('title')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L8)
            L6:     NOT_TAKEN
            L7:     POP_TOP
                    LOAD_CONST               6 ('No subject')
    
    3096    L8:     LOAD_CONST               7 ('sender')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST               7 ('sender')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        28 (to L13)
            L9:     NOT_TAKEN
           L10:     POP_TOP
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST               8 ('from_address')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L13)
           L11:     NOT_TAKEN
           L12:     POP_TOP
                    LOAD_CONST               9 ('Unknown')
    
    3097   L13:     LOAD_CONST              10 ('received')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST              11 ('received_at')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        18 (to L16)
           L14:     NOT_TAKEN
           L15:     POP_TOP
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST              12 ('created_at')
                    CALL                     1
    
    3098   L16:     LOAD_CONST              13 ('snippet')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST              13 ('snippet')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE        28 (to L21)
           L17:     NOT_TAKEN
           L18:     POP_TOP
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST              14 ('body')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L21)
           L19:     NOT_TAKEN
           L20:     POP_TOP
                    LOAD_CONST              15 ('')
           L21:     LOAD_CONST              16 (slice(None, 100, None))
                    BINARY_OP               26 ([])
    
    3099            LOAD_CONST              17 ('thread_id')
                    LOAD_FAST_BORROW         2 (e)
                    LOAD_ATTR                5 (get + NULL|self)
                    LOAD_CONST              17 ('thread_id')
                    CALL                     1
    
    3093            BUILD_MAP                6
                    LIST_APPEND              2
                    JUMP_BACKWARD          238 (to L3)
    
    3100   L22:     END_FOR
                    POP_ITER
    
    3093   L23:     SWAP                     2
                    STORE_FAST               2 (e)
    
    3101            LOAD_CONST              18 ('total')
                    LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                7 (count + NULL|self)
                    LOAD_CONST              19 ('communications')
                    LOAD_CONST              20 ('(processed = 0 OR processed IS NULL)')
                    CALL                     2
    
    3092            BUILD_MAP                2
                    RETURN_VALUE
    
      --   L24:     SWAP                     2
                    POP_TOP
    
    3093            SWAP                     2
                    STORE_FAST               2 (e)
                    RERAISE                  0
    
      --   L25:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L25 [0] lasti
      L2 to L4 -> L24 [3]
      L5 to L6 -> L24 [3]
      L7 to L9 -> L24 [3]
      L10 to L11 -> L24 [3]
      L12 to L14 -> L24 [3]
      L15 to L17 -> L24 [3]
      L18 to L19 -> L24 [3]
      L20 to L23 -> L24 [3]
      L23 to L25 -> L25 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/emails/{email_id}/dismiss")
async def dismiss_email(email_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3105
    
    3105           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3108           LOAD_GLOBAL              0 (store)
                   LOAD_ATTR                3 (update + NULL|self)
                   LOAD_CONST               1 ('communications')
                   LOAD_FAST_BORROW         0 (email_id)
                   LOAD_CONST               2 ('processed')
                   LOAD_SMALL_INT           1
                   BUILD_MAP                1
                   CALL                     3
                   POP_TOP
    
    3109           LOAD_CONST               3 ('success')
                   LOAD_CONST               4 (True)
                   LOAD_CONST               5 ('id')
                   LOAD_FAST_BORROW         0 (email_id)
                   BUILD_MAP                2
                   RETURN_VALUE
    
      --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L2 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/digest/weekly")
async def get_weekly_digest():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3116
    
    3116            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3119            LOAD_SMALL_INT           0
                    LOAD_CONST               1 (('date', 'timedelta'))
                    IMPORT_NAME              0 (datetime)
                    IMPORT_FROM              1 (date)
                    STORE_FAST               0 (date)
                    IMPORT_FROM              2 (timedelta)
                    STORE_FAST               1 (timedelta)
                    POP_TOP
    
    3121            LOAD_FAST_BORROW         0 (date)
                    LOAD_ATTR                7 (today + NULL|self)
                    CALL                     0
                    LOAD_FAST_BORROW         1 (timedelta)
                    PUSH_NULL
                    LOAD_SMALL_INT           7
                    LOAD_CONST               2 (('days',))
                    CALL_KW                  1
                    BINARY_OP               10 (-)
                    LOAD_ATTR                9 (isoformat + NULL|self)
                    CALL                     0
                    STORE_FAST               2 (week_ago)
    
    3123            LOAD_GLOBAL             10 (store)
                    LOAD_ATTR               13 (query + NULL|self)
                    LOAD_CONST               3 ("\n        SELECT * FROM tasks \n        WHERE status = 'completed' AND updated_at >= ?\n        ORDER BY updated_at DESC\n    ")
    
    3127            LOAD_FAST_BORROW         2 (week_ago)
                    BUILD_LIST               1
    
    3123            CALL                     2
                    STORE_FAST               3 (completed)
    
    3129            LOAD_GLOBAL             10 (store)
                    LOAD_ATTR               13 (query + NULL|self)
                    LOAD_CONST               4 ("\n        SELECT * FROM tasks \n        WHERE status = 'pending' AND due_date < date('now') AND due_date >= ?\n        ORDER BY due_date ASC\n    ")
    
    3133            LOAD_FAST_BORROW         2 (week_ago)
                    BUILD_LIST               1
    
    3129            CALL                     2
                    STORE_FAST               4 (slipped)
    
    3135            LOAD_GLOBAL             10 (store)
                    LOAD_ATTR               13 (query + NULL|self)
                    LOAD_CONST               5 ("\n        SELECT COUNT(*) as cnt FROM tasks \n        WHERE status = 'archived' AND updated_at >= ?\n    ")
    
    3138            LOAD_FAST_BORROW         2 (week_ago)
                    BUILD_LIST               1
    
    3135            CALL                     2
                    STORE_FAST               5 (archived)
    
    3141            LOAD_CONST               6 ('period')
                    LOAD_CONST               7 ('start')
                    LOAD_FAST_BORROW         2 (week_ago)
                    LOAD_CONST               8 ('end')
                    LOAD_FAST_BORROW         0 (date)
                    LOAD_ATTR                7 (today + NULL|self)
                    CALL                     0
                    LOAD_ATTR                9 (isoformat + NULL|self)
                    CALL                     0
                    BUILD_MAP                2
    
    3142            LOAD_CONST               9 ('completed')
    
    3143            LOAD_CONST              10 ('count')
                    LOAD_GLOBAL             15 (len + NULL)
                    LOAD_FAST_BORROW         3 (completed)
                    CALL                     1
    
    3144            LOAD_CONST              11 ('items')
    
    3148            LOAD_FAST_BORROW         3 (completed)
                    LOAD_CONST              12 (slice(None, 10, None))
                    BINARY_OP               26 ([])
                    GET_ITER
    
    3144            LOAD_FAST_AND_CLEAR      6 (t)
                    SWAP                     2
            L2:     BUILD_LIST               0
                    SWAP                     2
    
    3148    L3:     FOR_ITER                32 (to L4)
                    STORE_FAST               6 (t)
    
    3145            LOAD_CONST              13 ('id')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
    
    3146            LOAD_CONST              14 ('title')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              14 ('title')
                    BINARY_OP               26 ([])
    
    3147            LOAD_CONST              15 ('completed_at')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              16 ('updated_at')
                    BINARY_OP               26 ([])
    
    3144            BUILD_MAP                3
                    LIST_APPEND              2
                    JUMP_BACKWARD           34 (to L3)
    
    3148    L4:     END_FOR
                    POP_ITER
    
    3144    L5:     SWAP                     2
                    STORE_FAST               6 (t)
    
    3142            BUILD_MAP                2
    
    3150            LOAD_CONST              17 ('slipped')
    
    3151            LOAD_CONST              10 ('count')
                    LOAD_GLOBAL             15 (len + NULL)
                    LOAD_FAST_BORROW         4 (slipped)
                    CALL                     1
    
    3152            LOAD_CONST              11 ('items')
    
    3157            LOAD_FAST_BORROW         4 (slipped)
                    LOAD_CONST              12 (slice(None, 10, None))
                    BINARY_OP               26 ([])
                    GET_ITER
    
    3152            LOAD_FAST_AND_CLEAR      6 (t)
                    SWAP                     2
            L6:     BUILD_LIST               0
                    SWAP                     2
    
    3157    L7:     FOR_ITER                41 (to L8)
                    STORE_FAST               6 (t)
    
    3153            LOAD_CONST              13 ('id')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              13 ('id')
                    BINARY_OP               26 ([])
    
    3154            LOAD_CONST              14 ('title')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              14 ('title')
                    BINARY_OP               26 ([])
    
    3155            LOAD_CONST              18 ('due')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              19 ('due_date')
                    BINARY_OP               26 ([])
    
    3156            LOAD_CONST              20 ('assignee')
                    LOAD_FAST_BORROW         6 (t)
                    LOAD_CONST              20 ('assignee')
                    BINARY_OP               26 ([])
    
    3152            BUILD_MAP                4
                    LIST_APPEND              2
                    JUMP_BACKWARD           43 (to L7)
    
    3157    L8:     END_FOR
                    POP_ITER
    
    3152    L9:     SWAP                     2
                    STORE_FAST               6 (t)
    
    3150            BUILD_MAP                2
    
    3159            LOAD_CONST              21 ('archived')
                    LOAD_FAST_BORROW         5 (archived)
                    TO_BOOL
                    POP_JUMP_IF_FALSE       18 (to L12)
           L10:     NOT_TAKEN
           L11:     LOAD_FAST_BORROW         5 (archived)
                    LOAD_SMALL_INT           0
                    BINARY_OP               26 ([])
                    LOAD_CONST              22 ('cnt')
                    BINARY_OP               26 ([])
    
    3140            BUILD_MAP                4
                    RETURN_VALUE
    
    3159   L12:     LOAD_SMALL_INT           0
    
    3140            BUILD_MAP                4
                    RETURN_VALUE
    
      --   L13:     SWAP                     2
                    POP_TOP
    
    3144            SWAP                     2
                    STORE_FAST               6 (t)
                    RERAISE                  0
    
      --   L14:     SWAP                     2
                    POP_TOP
    
    3152            SWAP                     2
                    STORE_FAST               6 (t)
                    RERAISE                  0
    
      --   L15:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L15 [0] lasti
      L2 to L5 -> L13 [8]
      L5 to L6 -> L15 [0] lasti
      L6 to L9 -> L14 [10]
      L9 to L10 -> L15 [0] lasti
      L11 to L15 -> L15 [0] lasti
    """
    raise NotImplementedError

@app.post("/api/tasks/{task_id}/block")
async def add_blocker(task_id, body):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3171
    
    3171            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3174            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST_BORROW         0 (task_id)
                    CALL                     2
                    STORE_FAST               2 (task)
    
    3175            LOAD_FAST_BORROW         2 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    3176            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    3178    L2:     LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST_BORROW         1 (body)
                    LOAD_ATTR                6 (blocker_id)
                    CALL                     2
                    STORE_FAST               3 (blocker)
    
    3179            LOAD_FAST_BORROW         3 (blocker)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L5)
            L3:     NOT_TAKEN
    
    3180    L4:     LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               4 ('Blocker task not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    3183    L5:     NOP
    
    3184    L6:     LOAD_GLOBAL              8 (json)
                    LOAD_ATTR               10 (loads)
                    PUSH_NULL
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               5 ('blockers')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L9)
            L7:     NOT_TAKEN
            L8:     POP_TOP
                    LOAD_CONST               6 ('[]')
            L9:     CALL                     1
                    STORE_FAST               4 (current)
    
    3189   L10:     LOAD_FAST                1 (body)
                    LOAD_ATTR                6 (blocker_id)
                    LOAD_FAST                4 (current)
                    CONTAINS_OP              1 (not in)
                    POP_JUMP_IF_FALSE      108 (to L11)
                    NOT_TAKEN
    
    3190            LOAD_FAST                4 (current)
                    LOAD_ATTR               13 (append + NULL|self)
                    LOAD_FAST                1 (body)
                    LOAD_ATTR                6 (blocker_id)
                    CALL                     1
                    POP_TOP
    
    3191            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               15 (update + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST                0 (task_id)
    
    3192            LOAD_CONST               5 ('blockers')
                    LOAD_GLOBAL              8 (json)
                    LOAD_ATTR               16 (dumps)
                    PUSH_NULL
                    LOAD_FAST                4 (current)
                    CALL                     1
    
    3193            LOAD_CONST               7 ('updated_at')
                    LOAD_GLOBAL             18 (datetime)
                    LOAD_ATTR               20 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               23 (isoformat + NULL|self)
                    CALL                     0
    
    3191            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    3196   L11:     LOAD_CONST               8 ('success')
                    LOAD_CONST               9 (True)
                    LOAD_CONST               5 ('blockers')
                    LOAD_FAST                4 (current)
                    BUILD_MAP                2
                    RETURN_VALUE
    
      --   L12:     PUSH_EXC_INFO
    
    3185            POP_TOP
    
    3186            BUILD_LIST               0
                    STORE_FAST               4 (current)
           L13:     POP_EXCEPT
                    JUMP_BACKWARD_NO_INTERRUPT 136 (to L10)
    
      --   L14:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L15:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L15 [0] lasti
      L4 to L5 -> L15 [0] lasti
      L6 to L7 -> L12 [0]
      L8 to L10 -> L12 [0]
      L10 to L12 -> L15 [0] lasti
      L12 to L13 -> L14 [1] lasti
      L13 to L15 -> L15 [0] lasti
    """
    raise NotImplementedError

@app.delete("/api/tasks/{task_id}/block/{blocker_id}")
async def remove_blocker(task_id, blocker_id):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3199
    
    3199            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3202            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST_BORROW         0 (task_id)
                    CALL                     2
                    STORE_FAST               2 (task)
    
    3203            LOAD_FAST_BORROW         2 (task)
                    TO_BOOL
                    POP_JUMP_IF_TRUE        13 (to L2)
                    NOT_TAKEN
    
    3204            LOAD_GLOBAL              5 (HTTPException + NULL)
                    LOAD_CONST               2 (404)
                    LOAD_CONST               3 ('Task not found')
                    CALL                     2
                    RAISE_VARARGS            1
    
    3206    L2:     NOP
    
    3207    L3:     LOAD_GLOBAL              6 (json)
                    LOAD_ATTR                8 (loads)
                    PUSH_NULL
                    LOAD_FAST_BORROW         2 (task)
                    LOAD_ATTR                3 (get + NULL|self)
                    LOAD_CONST               4 ('blockers')
                    CALL                     1
                    COPY                     1
                    TO_BOOL
                    POP_JUMP_IF_TRUE         3 (to L6)
            L4:     NOT_TAKEN
            L5:     POP_TOP
                    LOAD_CONST               5 ('[]')
            L6:     CALL                     1
                    STORE_FAST               3 (current)
    
    3211    L7:     LOAD_FAST_LOAD_FAST     19 (blocker_id, current)
                    CONTAINS_OP              0 (in)
                    POP_JUMP_IF_FALSE       98 (to L8)
                    NOT_TAKEN
    
    3212            LOAD_FAST                3 (current)
                    LOAD_ATTR               11 (remove + NULL|self)
                    LOAD_FAST                1 (blocker_id)
                    CALL                     1
                    POP_TOP
    
    3213            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR               13 (update + NULL|self)
                    LOAD_CONST               1 ('tasks')
                    LOAD_FAST                0 (task_id)
    
    3214            LOAD_CONST               4 ('blockers')
                    LOAD_GLOBAL              6 (json)
                    LOAD_ATTR               14 (dumps)
                    PUSH_NULL
                    LOAD_FAST                3 (current)
                    CALL                     1
    
    3215            LOAD_CONST               6 ('updated_at')
                    LOAD_GLOBAL             16 (datetime)
                    LOAD_ATTR               18 (now)
                    PUSH_NULL
                    CALL                     0
                    LOAD_ATTR               21 (isoformat + NULL|self)
                    CALL                     0
    
    3213            BUILD_MAP                2
                    CALL                     3
                    POP_TOP
    
    3218    L8:     LOAD_CONST               7 ('success')
                    LOAD_CONST               8 (True)
                    LOAD_CONST               4 ('blockers')
                    LOAD_FAST                3 (current)
                    BUILD_MAP                2
                    RETURN_VALUE
    
      --    L9:     PUSH_EXC_INFO
    
    3208            POP_TOP
    
    3209            BUILD_LIST               0
                    STORE_FAST               3 (current)
           L10:     POP_EXCEPT
                    JUMP_BACKWARD_NO_INTERRUPT 115 (to L7)
    
      --   L11:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L12:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L2 -> L12 [0] lasti
      L3 to L4 -> L9 [0]
      L5 to L7 -> L9 [0]
      L7 to L9 -> L12 [0] lasti
      L9 to L10 -> L11 [1] lasti
      L10 to L12 -> L12 [0] lasti
    """
    raise NotImplementedError

@app.get("/api/dependencies")
async def get_dependencies():
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3221
    
    3221            RETURN_GENERATOR
                    POP_TOP
            L1:     RESUME                   0
    
    3224            LOAD_GLOBAL              0 (store)
                    LOAD_ATTR                3 (query + NULL|self)
                    LOAD_CONST               1 ("\n        SELECT * FROM tasks \n        WHERE status = 'pending' AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'\n        ORDER BY priority DESC\n    ")
                    CALL                     1
                    STORE_FAST               0 (blocked)
    
    3231            LOAD_GLOBAL              5 (set + NULL)
                    CALL                     0
                    STORE_FAST               1 (blocking_ids)
    
    3232            LOAD_FAST_BORROW         0 (blocked)
                    GET_ITER
            L2:     FOR_ITER               157 (to L13)
                    STORE_FAST               2 (t)
    
    3233    L3:     NOP
    
    3234    L4:     LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               2 ('blockers')
                    BINARY_OP               26 ([])
                    TO_BOOL
                    POP_JUMP_IF_FALSE       30 (to L5)
                    NOT_TAKEN
                    LOAD_GLOBAL              6 (json)
                    LOAD_ATTR                8 (loads)
                    PUSH_NULL
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               2 ('blockers')
                    BINARY_OP               26 ([])
                    CALL                     1
                    JUMP_FORWARD             1 (to L6)
            L5:     BUILD_LIST               0
            L6:     STORE_FAST               3 (blockers)
    
    3235            LOAD_FAST_BORROW         3 (blockers)
                    GET_ITER
            L7:     FOR_ITER               101 (to L11)
                    STORE_FAST               4 (b)
    
    3236            LOAD_GLOBAL             11 (isinstance + NULL)
                    LOAD_FAST_BORROW         4 (b)
                    LOAD_GLOBAL             12 (str)
                    CALL                     2
                    TO_BOOL
                    POP_JUMP_IF_FALSE       20 (to L8)
                    NOT_TAKEN
    
    3237            LOAD_FAST_BORROW         1 (blocking_ids)
                    LOAD_ATTR               15 (add + NULL|self)
                    LOAD_FAST_BORROW         4 (b)
                    CALL                     1
                    POP_TOP
                    JUMP_BACKWARD           44 (to L7)
    
    3238    L8:     LOAD_GLOBAL             11 (isinstance + NULL)
                    LOAD_FAST_BORROW         4 (b)
                    LOAD_GLOBAL             16 (dict)
                    CALL                     2
                    TO_BOOL
            L9:     POP_JUMP_IF_TRUE         3 (to L10)
                    NOT_TAKEN
                    JUMP_BACKWARD           68 (to L7)
    
    3239   L10:     LOAD_FAST_BORROW         1 (blocking_ids)
                    LOAD_ATTR               15 (add + NULL|self)
                    LOAD_FAST_BORROW         4 (b)
                    LOAD_ATTR               19 (get + NULL|self)
                    LOAD_CONST               3 ('id')
                    LOAD_CONST               4 ('')
                    CALL                     2
                    CALL                     1
                    POP_TOP
                    JUMP_BACKWARD          103 (to L7)
    
    3235   L11:     END_FOR
                    POP_ITER
           L12:     JUMP_BACKWARD          159 (to L2)
    
    3232   L13:     END_FOR
                    POP_ITER
    
    3244            LOAD_CONST               5 ('blocked')
    
    3250            LOAD_FAST_BORROW         0 (blocked)
                    GET_ITER
    
    3244            LOAD_FAST_AND_CLEAR      2 (t)
                    SWAP                     2
           L14:     BUILD_LIST               0
                    SWAP                     2
    
    3250   L15:     FOR_ITER                50 (to L16)
                    STORE_FAST               2 (t)
    
    3245            LOAD_CONST               3 ('id')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               3 ('id')
                    BINARY_OP               26 ([])
    
    3246            LOAD_CONST               6 ('title')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               6 ('title')
                    BINARY_OP               26 ([])
    
    3247            LOAD_CONST               2 ('blockers')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               2 ('blockers')
                    BINARY_OP               26 ([])
    
    3248            LOAD_CONST               7 ('assignee')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               7 ('assignee')
                    BINARY_OP               26 ([])
    
    3249            LOAD_CONST               8 ('due')
                    LOAD_FAST_BORROW         2 (t)
                    LOAD_CONST               9 ('due_date')
                    BINARY_OP               26 ([])
    
    3244            BUILD_MAP                5
                    LIST_APPEND              2
                    JUMP_BACKWARD           52 (to L15)
    
    3250   L16:     END_FOR
                    POP_ITER
    
    3244   L17:     SWAP                     2
                    STORE_FAST               2 (t)
    
    3251            LOAD_CONST              10 ('blocking_count')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         1 (blocking_ids)
                    CALL                     1
    
    3252            LOAD_CONST              11 ('total_blocked')
                    LOAD_GLOBAL             21 (len + NULL)
                    LOAD_FAST_BORROW         0 (blocked)
                    CALL                     1
    
    3243            BUILD_MAP                3
                    RETURN_VALUE
    
      --   L18:     PUSH_EXC_INFO
    
    3240            POP_TOP
    
    3241   L19:     POP_EXCEPT
                    JUMP_BACKWARD          253 (to L2)
    
      --   L20:     COPY                     3
                    POP_EXCEPT
                    RERAISE                  1
           L21:     SWAP                     2
                    POP_TOP
    
    3244            SWAP                     2
                    STORE_FAST               2 (t)
                    RERAISE                  0
    
      --   L22:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                    RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L22 [0] lasti
      L4 to L9 -> L18 [1]
      L10 to L12 -> L18 [1]
      L12 to L14 -> L22 [0] lasti
      L14 to L17 -> L21 [3]
      L17 to L18 -> L22 [0] lasti
      L18 to L19 -> L20 [2] lasti
      L19 to L22 -> L22 [0] lasti
    """
    raise NotImplementedError

@app.get("/{path:path}")
async def spa_fallback(path):
    """
    Original: /Users/molhamhomsi/clawd/moh_time_os/api/server.py:3260
    
    3260           RETURN_GENERATOR
                   POP_TOP
           L1:     RESUME                   0
    
    3264           LOAD_FAST_BORROW         0 (path)
                   LOAD_ATTR                1 (startswith + NULL|self)
                   LOAD_CONST               1 ('api/')
                   CALL                     1
                   TO_BOOL
                   POP_JUMP_IF_FALSE       14 (to L2)
                   NOT_TAKEN
    
    3265           LOAD_GLOBAL              3 (HTTPException + NULL)
                   LOAD_CONST               2 (404)
                   LOAD_CONST               3 ('Not Found')
                   LOAD_CONST               4 (('status_code', 'detail'))
                   CALL_KW                  2
                   RAISE_VARARGS            1
    
    3266   L2:     LOAD_GLOBAL              5 (FileResponse + NULL)
                   LOAD_GLOBAL              6 (UI_DIR)
                   LOAD_CONST               5 ('index.html')
                   BINARY_OP               11 (/)
                   CALL                     1
                   RETURN_VALUE
    
      --   L3:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
                   RERAISE                  1
    ExceptionTable:
      L1 to L3 -> L3 [0] lasti
    """
    raise NotImplementedError

