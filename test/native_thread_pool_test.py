import datetime
import os, sys
from unittest import mock
import unittest
import logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

global ThreadPool
global sleep
global Queue
global Full
global ExitException


class NativeThreadPoolTest(unittest.TestCase):

    thread_type = ''

    @classmethod
    def setUpClass(cls) -> None:
        global ThreadPool
        global sleep
        global Queue
        global Full
        global ExitException
        from native_thread_pool import NativeThreadPool as _ThreadPool
        ThreadPool = _ThreadPool
        from time import sleep as _sleep
        sleep = _sleep
        from queue import Queue as _Queue, Full as _Full
        Queue = _Queue
        Full = _Full
        ExitException = SystemExit

    def func_with_args_and_kwargs(self, param, *args, **kwargs):
        return ','.join([str(param), str(args), str(kwargs)])

    def func_with_sleep(self, param, sleep_second=0.1):
        sleep(sleep_second)
        logging.info(f'param: {param}')
        return param

    def func_with_sleep_and_exception(self, sleep_second=0.1):
        sleep(sleep_second)
        raise RuntimeError("Not Killed")

    def func_with_sleep_and_exception_and_update_list(self, a_list, sleep_second=0.1):
        assert len(a_list) == 1
        sleep(sleep_second)
        a_list[0] += 1
        logging.info(f'add !!!!!!!')
        raise RuntimeError("Not Killed")

    def func_for_test_concurrency(self, q, sleep_second=0.1):
        q.put('', block=False)
        sleep(sleep_second)
        q.get(block=False)

    def func_for_test_execute(self, queue, sleep_second=0.1):
        sleep(sleep_second)
        queue.put('')

    def test_thread_pool_should_get_results_order_by_index(self):
        pool = ThreadPool(total_thread_number=2)
        pool.apply_async(self.func_with_args_and_kwargs, args=(1, 2, 3), kwargs=dict(a=4, b=5))
        pool.apply_async(self.func_with_args_and_kwargs, args=(11, 22, 33), kwargs=dict(a=44, b=55))
        res = pool.get_results_order_by_index(with_status=False, raise_exception=True)
        self.assertEqual("1,(2, 3),{'a': 4, 'b': 5}", res[0])
        self.assertEqual("11,(22, 33),{'a': 44, 'b': 55}", res[1])

        pool.refresh()
        pool.apply_async(self.func_with_args_and_kwargs, args=(1, 2, 3), kwargs=dict(a=4, b=5))
        pool.apply_async(self.func_with_args_and_kwargs, args=(11, 22, 33), kwargs=dict(a=44, b=55))
        res = pool.get_results_order_by_index(with_status=True, raise_exception=True)
        self.assertEqual((True, "1,(2, 3),{'a': 4, 'b': 5}"), res[0])
        self.assertEqual((True, "11,(22, 33),{'a': 44, 'b': 55}"), res[1])

        pool.refresh()
        pool.apply_async(self.func_with_args_and_kwargs, args=(1, 2, 3), kwargs=dict(a=4, b=5))
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        res = pool.get_results_order_by_index(with_status=True, raise_exception=False)
        self.assertEqual((True, "1,(2, 3),{'a': 4, 'b': 5}"), res[0])
        self.assertEqual(False, res[1][0])
        self.assertEqual(RuntimeError, type(res[1][1]))

        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        with self.assertRaises((RuntimeError,)):
            pool.get_results_order_by_index(raise_exception=True, stop_all_for_exception=False)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        with self.assertRaises((RuntimeError,)):
            pool.get_results_order_by_index(raise_exception=True, stop_all_for_exception=True)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        pool.get_results_order_by_index(raise_exception=False, stop_all_for_exception=False)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        pool.get_results_order_by_index(raise_exception=False, stop_all_for_exception=True)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

    def test_thread_pool_should_get_results_order_by_time(self):
        pool = ThreadPool(total_thread_number=2)
        start_time = datetime.datetime.now()
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.1))

        res = pool.get_results_order_by_time(with_status=False, with_index=False)
        self.assertEqual(2, next(res))
        self.assertAlmostEqual(0.1, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)
        self.assertEqual(1, next(res))
        self.assertAlmostEqual(0.2, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)

        pool.refresh()
        start_time = datetime.datetime.now()
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.1))

        res = pool.get_results_order_by_time(with_status=True, with_index=False)
        self.assertEqual((True, 2), next(res))
        self.assertAlmostEqual(0.1, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)
        self.assertEqual((True, 1), next(res))
        self.assertAlmostEqual(0.2, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)

        pool.refresh()
        start_time = datetime.datetime.now()
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.1))

        res = pool.get_results_order_by_time(with_status=False, with_index=True)
        self.assertEqual((1, 2), next(res))
        self.assertAlmostEqual(0.1, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)
        self.assertEqual((0, 1), next(res))
        self.assertAlmostEqual(0.2, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)

        pool.refresh()
        start_time = datetime.datetime.now()
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.1))

        res = pool.get_results_order_by_time(with_status=True, with_index=True)
        self.assertEqual((1, True, 2), next(res))
        self.assertAlmostEqual(0.1, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)
        self.assertEqual((0, True, 1), next(res))
        self.assertAlmostEqual(0.2, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)

        pool.refresh()
        start_time = datetime.datetime.now()
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.1))

        res = pool.get_results_order_by_time(with_status=True, with_index=True)
        self.assertEqual((1, True, 2), next(res))
        self.assertAlmostEqual(0.1, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)
        self.assertEqual((0, True, 1), next(res))
        self.assertAlmostEqual(0.2, (datetime.datetime.now() - start_time).microseconds / 1000000, delta=0.1)

        pool.refresh()
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        res = pool.get_results_order_by_time(raise_exception=True, )
        with self.assertRaises((RuntimeError,)):
            next(res)

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        res = pool.get_results_order_by_time(raise_exception=True, stop_all_for_exception=True)
        with self.assertRaises((RuntimeError,)):
            next(res)
        self.assertEqual(0, queue.qsize())

        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        res = pool.get_results_order_by_time(raise_exception=True, stop_all_for_exception=False)
        with self.assertRaises((RuntimeError,)):
            next(res)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        res = pool.get_results_order_by_time(raise_exception=True, stop_all_for_exception=True)
        with self.assertRaises((RuntimeError,)):
            next(res)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        res = pool.get_results_order_by_time(raise_exception=False, stop_all_for_exception=False)
        next(res)
        next(res)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        res = pool.get_results_order_by_time(raise_exception=False, stop_all_for_exception=True)
        next(res)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

    def test_thread_pool_should_wait_all_threads(self):
        pool = ThreadPool(total_thread_number=2)

        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        with self.assertRaises((RuntimeError,)):
            pool.wait_all_threads(raise_exception=True, stop_all_for_exception=False)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        with self.assertRaises((RuntimeError,)):
            pool.wait_all_threads(raise_exception=True, stop_all_for_exception=True)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        pool.wait_all_threads(raise_exception=False, stop_all_for_exception=False)
        sleep(0.2)
        self.assertEqual(1, queue.qsize())

        pool.refresh()
        queue = Queue(maxsize=4)
        pool.apply_async(self.func_with_sleep_and_exception, args=(0.01,))
        pool.apply_async(self.func_for_test_execute, args=(queue,), kwargs=dict(sleep_second=0.1))
        pool.wait_all_threads(raise_exception=False, stop_all_for_exception=True)
        sleep(0.2)
        self.assertEqual(0, queue.qsize())

    def test_thread_pool_should_block_new_async_job_when_pool_full(self):
        for total_thread_number in range(1, 20):
            pool = ThreadPool(total_thread_number=total_thread_number)
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number + 1):
                pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number + 1)
            q = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number + 1):
                pool.apply_async(self.func_for_test_concurrency, args=(q,))
            with self.assertRaises((Full,)):
                pool.wait_all_threads(raise_exception=True)

    def test_thread_pool_should_share_pool_with_same_capacity(self):
        for total_thread_number in range(4, 20, 2):
            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool()
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number // 2 + 1):
                pool.apply_async(self.func_for_test_concurrency, args=(queue,))
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            pool.wait_all_threads(raise_exception=True)
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool()
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number + 1):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool()
            queue = Queue(maxsize=total_thread_number - 1)
            for _ in range(total_thread_number):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            with self.assertRaises((Full,)):
                shared_pool.wait_all_threads(raise_exception=True)

    def test_thread_pool_should_share_pool_with_smaller_capacity(self):
        for total_thread_number in range(4, 20, 2):
            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number - 1)
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number // 2 + 1):
                pool.apply_async(self.func_for_test_concurrency, args=(queue,))
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            pool.wait_all_threads(raise_exception=True)
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number - 1)
            queue = Queue(maxsize=total_thread_number - 1)
            for _ in range(total_thread_number - 1):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number - 1)
            queue = Queue(maxsize=total_thread_number - 2)
            for _ in range(total_thread_number - 1):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            with self.assertRaises((Full,)):
                shared_pool.wait_all_threads(raise_exception=True)

    def test_thread_pool_should_share_pool_with_larger_capacity(self):
        for total_thread_number in range(4, 20, 2):
            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number + 1)
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number // 2 + 1):
                pool.apply_async(self.func_for_test_concurrency, args=(queue,))
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            pool.wait_all_threads(raise_exception=True)
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number + 1)
            queue = Queue(maxsize=total_thread_number)
            for _ in range(total_thread_number + 1):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            shared_pool.wait_all_threads(raise_exception=True)

            pool = ThreadPool(total_thread_number=total_thread_number)
            shared_pool = pool.new_shared_pool(total_thread_number + 1)
            queue = Queue(maxsize=total_thread_number - 1)
            for _ in range(total_thread_number):
                shared_pool.apply_async(self.func_for_test_concurrency, args=(queue,))
            with self.assertRaises((Full,)):
                shared_pool.wait_all_threads(raise_exception=True)

    def test_thread_pool_should_reuse_pool_after_stop_threads(self):
        pool = ThreadPool(total_thread_number=2)

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        pool.stop_all()
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        pool.get_results_order_by_index()
        self.assertEqual([4], a_list)

    def test_thread_pool_should_get_result_by_index_after_kill_one_and_get_one_result(self):
        pool = ThreadPool(total_thread_number=4, exit_for_any_exception=True)
        pool.apply_async(self.func_with_sleep_and_exception, kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.3))
        pool.apply_async(self.func_with_sleep, args=(3,), kwargs=dict(sleep_second=0.4))
        pool.stop_nth_thread(0)
        quickest_result = pool.get_one_result(raise_exception=True)
        self.assertEqual(1, quickest_result)
        results = pool.get_results_order_by_index(raise_exception=True)
        self.assertEqual(2, results[2])
        self.assertEqual(3, results[3])

    def test_thread_pool_should_get_result_by_time_after_kill_one_and_get_one_result(self):
        pool = ThreadPool(total_thread_number=4, exit_for_any_exception=True)
        pool.apply_async(self.func_with_sleep_and_exception, kwargs=dict(sleep_second=0.1))
        pool.apply_async(self.func_with_sleep, args=(1,), kwargs=dict(sleep_second=0.2))
        pool.apply_async(self.func_with_sleep, args=(2,), kwargs=dict(sleep_second=0.4))
        pool.apply_async(self.func_with_sleep, args=(3,), kwargs=dict(sleep_second=0.3))
        pool.stop_nth_thread(0)
        quickest_result = pool.get_one_result(raise_exception=True)
        self.assertEqual(1, quickest_result)
        expected_result_by_time = [3, 2]
        actual_result_by_time = []
        for index, res in enumerate(pool.get_results_order_by_time(raise_exception=True)):
            actual_result_by_time.append(res)
        logging.info(expected_result_by_time)
        logging.info(actual_result_by_time)
        self.assertEqual(expected_result_by_time, actual_result_by_time)

    def test_thread_pool_should_raise_exception_when_any_exception_happen(self):
        pool = ThreadPool(total_thread_number=2, exit_for_any_exception=False)

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.2))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            pool.get_results_order_by_index(raise_exception=True, stop_all_for_exception=False)
        sleep(0.3)
        assert a_list[0] == 3

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.2))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            for _ in pool.get_results_order_by_time(raise_exception=True, stop_all_for_exception=False):
                pass
        sleep(0.3)
        assert a_list[0] == 3

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.2))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            pool.get_one_result(raise_exception=True, stop_all_for_exception=False)
        sleep(0.3)
        assert a_list[0] == 3
        pool.refresh()

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.3))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            pool.get_results_order_by_index(raise_exception=True, stop_all_for_exception=True)
        sleep(0.4)
        assert a_list[0] == 2

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.3))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            for _ in pool.get_results_order_by_time(raise_exception=True, stop_all_for_exception=True):
                pass
        sleep(0.4)
        assert a_list[0] == 2

        a_list = [1]
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        pool.apply_async(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.3))
        with self.assertRaisesRegex(RuntimeError, "^Not Killed$"):
            pool.get_one_result(raise_exception=True, stop_all_for_exception=True)
        sleep(0.4)
        assert a_list[0] == 2

    def test_thread_pool_should_exit_program_when_any_exception_happen(self):

        os._exit = mock.Mock()
        sys.exit = os._exit

        pool = ThreadPool(total_thread_number=1, exit_for_any_exception=True)
        pool.apply_async(self.func_with_sleep_and_exception, kwargs=dict(sleep_second=0.1))

        try:
            pool.get_results_order_by_index(raise_exception=True)
        except:
            pass
        os._exit.assert_called_once()

        os._exit = mock.Mock()
        sys.exit = os._exit

        pool = ThreadPool(total_thread_number=1).new_shared_pool(exit_for_any_exception=True)
        pool.apply_async(self.func_with_sleep_and_exception, kwargs=dict(sleep_second=0.1))

        try:
            pool.get_results_order_by_index(raise_exception=True)
        except:
            pass
        os._exit.assert_called_once()

    def test_should_start_new_thread(self):
        a_list = [1]
        ThreadPool.new_thread(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        ThreadPool.new_thread(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0))
        sleep(0.1)
        assert a_list[0] == 3

        a_list = [1]
        th_1 = ThreadPool.new_thread(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        th_2 = ThreadPool.new_thread(self.func_with_sleep_and_exception_and_update_list, args=(a_list,), kwargs=dict(sleep_second=0.1))
        th_1.kill()
        sleep(0.2)
        assert a_list[0] == 2

    def test_should_do_clean_job(self):

        def clean(res):
            try:
                sleep(0.1)
                res.append('finish')
            except ExitException:
                res.append('clean')

        res = []
        pool = ThreadPool(total_thread_number=1)
        pool.apply_async(clean, args=(res,))
        pool.get_results_order_by_index()
        self.assertEqual(['finish'], res)

        res = []
        pool = ThreadPool(total_thread_number=1)
        pool.apply_async(clean, args=(res,))
        sleep(0.01)
        pool.stop_nth_thread(0)
        sleep(0.2)
        pool.get_results_order_by_index()
        self.assertEqual(['clean'], res)
