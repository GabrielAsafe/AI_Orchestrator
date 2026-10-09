from .cli import main
if __name__ == '__main__':
    import sys
    try:
        sys.exit(main())
    except (ValueError,PermissionError,FileNotFoundError,RuntimeError,KeyError) as exc:
        print('%s: %s' % (type(exc).__name__,exc),file=sys.stderr)
        sys.exit(2)
