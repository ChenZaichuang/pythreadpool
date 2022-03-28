#!/usr/bin/env python
# -*- coding:utf-8 -*-

#############################################
# File Name: setup.py
# Author: ChenZaichuang
# Mail: 1158400735@qq.com
# Created Time:  2021-1-14 14:00:00
#############################################

from setuptools import setup, find_packages

setup(
    name="pythreadpool",
    version="1.0.6",
    keywords=("pip", "pythreadpool", "thread pool"),
    description="Thread pool for async jobs manage",
    long_description="Provide unified api of native thread and gevent, make it easy to manage async jobs",
    license="MIT Licence",

    url="https://github.com/ChenZaichuang/pythreadpool",
    author="ChenZaichuang",
    author_email="1158400735@qq.com",

    packages=find_packages(),
    include_package_data=True,
    platforms="any",
    install_requires=[]
)
