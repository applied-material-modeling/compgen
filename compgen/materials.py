class FixedMaterialGenerator:
    """
    Just return a fixed dictionary of material properties.

    Args:
        props (dict): A dictionary of material properties.
    """

    def __init__(self, **props):
        self.props = props

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        return self.props
