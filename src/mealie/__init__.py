from .categories import CategoriesMixin
from .client import MealieClient
from .cookbooks import CookbooksMixin
from .foods import FoodsMixin
from .group import GroupMixin
from .labels import LabelsMixin
from .mealplan import MealplanMixin
from .organizers import OrganizersMixin
from .parser import ParserMixin
from .recipe import RecipeMixin
from .shopping_list import ShoppingListMixin
from .tags import TagsMixin
from .tools import ToolsMixin
from .units import UnitsMixin
from .user import UserMixin


class MealieFetcher(
    RecipeMixin,
    CategoriesMixin,
    TagsMixin,
    FoodsMixin,
    LabelsMixin,
    UnitsMixin,
    ToolsMixin,
    OrganizersMixin,
    ParserMixin,
    ShoppingListMixin,
    MealplanMixin,
    CookbooksMixin,
    UserMixin,
    GroupMixin,
    MealieClient,
):
    pass
