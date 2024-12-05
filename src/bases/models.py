from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    pass


class IngameModel(PydanticBaseModel):
    data: str

    def to_dict(self, **kwargs) -> dict:
        return self.model_dump(**kwargs)

    @staticmethod
    def find_index(data: list[str],
                   query: list[str],
                   offset: int = None,
                   limit: int = None):

        if not offset:
            offset = 0

        if not limit:
            limit = len(data)

        result = None
        length = len(query)
        data_to_search = data[offset:limit]
        for index, byte in enumerate(data_to_search):
            check_value = data_to_search[index: length + index]
            if len(check_value) < length:
                break

            if check_value == query:
                result = index
                break

        if result is None:
            return None

        return offset + result


