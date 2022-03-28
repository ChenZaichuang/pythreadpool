import ctypes
import logging
import os
import queue
from queue import Queue
import traceback
import threading
from threading import BoundedSemaphore


class ThreadTimeout(Exception):
    pass


class ThreadWithException(threading.Thread):

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)

    def kill(self):
        if not self.is_alive():
            return
        thread_id = ctypes.c_long(self.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res == 0:
            raise ValueError('nonexistent thread id')
        elif res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            raise SystemError('PyThreadState_SetAsyncExc failed')


class NativeThreadPool:

    __slots__ = ('max_thread', 'main_semaphore', 'sub_semaphore', 'exit_for_any_exception',
                 '_thread_res_queue', 'valid_for_new_thread', 'log_exception', 'thread_list',
                 'completed_threads', 'killed_threads', 'raise_exception', 'happened_exception')

    def __init__(self, **kwargs):
        assert 'total_thread_number' in kwargs or ('semaphore' in kwargs and 'max_thread' in kwargs)
        if 'total_thread_number' in kwargs:
            self.max_thread = kwargs['total_thread_number']
            self.main_semaphore = BoundedSemaphore(self.max_thread)
            self.sub_semaphore = BoundedSemaphore(self.max_thread)
        else:
            self.max_thread = kwargs['max_thread']
            self.main_semaphore = kwargs['semaphore']
            self.sub_semaphore = BoundedSemaphore(self.max_thread)
        self.exit_for_any_exception = kwargs.get("exit_for_any_exception", False)
        self.raise_exception = kwargs.get("raise_exception", False)
        self.valid_for_new_thread = True
        self._thread_res_queue = Queue()
        self.happened_exception = None
        self.log_exception = kwargs.get('log_exception', True)
        if self.raise_exception:
            self.log_exception = True
        self.thread_list = []
        self.completed_threads = set()
        self.killed_threads = set()

    def start_thread(self, thread_number, func, args, kwargs):
        success = True
        res = None
        main_semaphore = self.main_semaphore
        sub_semaphore = self.sub_semaphore
        thread_res_queue = self._thread_res_queue
        completed_threads = self.completed_threads
        killed_threads = self.killed_threads
        try:
            res = func(*args, **kwargs)
        except Exception as e:
            self.happened_exception = e
            res = e
            err_msg = traceback.format_exc()
            if self.log_exception:
                logging.error(f"Thread {thread_number} failed, error msg: \n{err_msg}")
            if self.exit_for_any_exception:
                os._exit(-1)
            success = False
        finally:
            main_semaphore.release()
            sub_semaphore.release()
            completed_threads.add(thread_number)
            if thread_number not in killed_threads:
                thread_res_queue.put((thread_number, success, res))

    def apply_async(self, func, args=None, kwargs=None, daemon=True):
        assert self.valid_for_new_thread
        if self.raise_exception and self.happened_exception is not None:
            raise self.happened_exception
        self.main_semaphore.acquire()
        self.sub_semaphore.acquire()
        if args is None:
            args = tuple()
        if kwargs is None:
            kwargs = dict()
        thread = ThreadWithException(target=self.start_thread, args=(len(self.thread_list), func, args, kwargs), daemon=daemon)
        self.thread_list.append(thread)
        thread.start()
        return thread

    def new_shared_pool(self, max_thread=0, exit_for_any_exception=False):
        return NativeThreadPool(semaphore=self.main_semaphore, exit_for_any_exception=exit_for_any_exception,
                                max_thread=max_thread if max_thread > 0 else self.max_thread)

    def get_results_order_by_index(self, raise_exception=False, with_status=False, stop_all_for_exception=False, with_index=False):
        self.valid_for_new_thread = False
        threads_result = [('', '')] * len(self.thread_list) if with_status else [''] * len(self.thread_list)
        for index in range(len(self.thread_list) - len(self.killed_threads)):
            thread_number, success, res = self._thread_res_queue.get()
            should_break = False

            if thread_number in self.killed_threads:
                continue

            if not success:
                if stop_all_for_exception:
                    should_break = True
                    self.stop_all()
                if raise_exception:
                    self.refresh()
                    raise res

            if with_index:
                threads_result[thread_number] = (thread_number, success, res) if with_status else (thread_number, res)
            else:
                threads_result[thread_number] = (success, res) if with_status else res

            if should_break:
                break

        self.refresh()
        return threads_result

    def get_results_order_by_time(self, raise_exception=False, with_status=False, with_index=False, stop_all_for_exception=False):
        self.valid_for_new_thread = False
        for index in range(len(self.thread_list) - len(self.killed_threads)):
            thread_number, success, res = self._thread_res_queue.get()
            should_break = False
            if not success:
                if stop_all_for_exception:
                    should_break = True
                    self.stop_all()
                if raise_exception:
                    self.refresh()
                    raise res

            if with_index:
                yield (thread_number, success, res) if with_status else (thread_number, res)
            else:
                yield (success, res) if with_status else res

            if should_break:
                break

    def get_one_result(self, raise_exception=False, with_status=False, with_index=False, stop_all_for_exception=False, timeout=None):
        while True:
            try:
                thread_number, success, res = self._thread_res_queue.get(timeout=timeout)
                if thread_number in self.killed_threads:
                    continue
                self.killed_threads.add(thread_number)
                if not success:
                    if stop_all_for_exception:
                        self.stop_all()
                    if raise_exception:
                        raise res
                if with_index:
                    return (thread_number, success, res) if with_status else (thread_number, res)
                else:
                    return (success, res) if with_status else res
            except queue.Empty:
                raise ThreadTimeout(f'Thread timeout after {timeout} seconds')

    def wait_all_threads(self, raise_exception=False, stop_all_for_exception=False):
        for _ in range(len(self.thread_list) - len(self.killed_threads)):
            thread_number, success, res = self._thread_res_queue.get()
            should_break = False
            if not success:
                if stop_all_for_exception:
                    should_break = True
                    self.stop_all()
                if raise_exception:
                    self.refresh()
                    raise res
            if should_break:
                break
        self.refresh()

    def stop_all(self):
        for index in range(len(self.thread_list)):
            self.stop_nth_thread(index)

    def stop_nth_thread(self, n):
        if n not in self.completed_threads:

            self.completed_threads.add(n)
            self.killed_threads.add(n)
            self.thread_list[n].kill()

    def refresh(self):
        self.thread_list = []
        self.valid_for_new_thread = True
        self.completed_threads = set()
        self.killed_threads = set()
        self._thread_res_queue = Queue()
        self.happened_exception = None

    @classmethod
    def new_thread(cls, target, args=None, kwargs=None, daemon=True):
        args = args if args is not None else tuple()
        kwargs = kwargs if kwargs is not None else dict()
        def start():
            target(*args, **kwargs)
        th = ThreadWithException(target=start, daemon=daemon)
        th.start()
        return th
