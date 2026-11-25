"""Versioned API routes for served callers."""

from fastapi import params

segment = "v1"

dependencies: tuple[params.Depends, ...] = ()
