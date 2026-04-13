from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.deps import DbSession
from app.models import DeliveryProfile, GenerationProfile, Newsletter


@dataclass(frozen=True)
class ResolvedGenerationProfile:
    profile: GenerationProfile | None
    provider_id: int | None
    model_name: str | None
    api_key_id: int | None
    binding_mode: str | None


@dataclass(frozen=True)
class ResolvedDeliveryProfile:
    profile: DeliveryProfile | None
    api_key_id: int | None
    from_email: str | None
    binding_mode: str | None


def resolve_generation_profile(db: DbSession, newsletter: Newsletter) -> ResolvedGenerationProfile:
    profile = None
    if newsletter.generation_profile_id is not None:
        profile = db.scalar(
            select(GenerationProfile).where(
                GenerationProfile.id == newsletter.generation_profile_id
            )
        )

    if profile is None:
        return ResolvedGenerationProfile(
            profile=None,
            provider_id=newsletter.provider_id,
            model_name=newsletter.model_name,
            api_key_id=newsletter.api_key_id,
            binding_mode=None,
        )

    return ResolvedGenerationProfile(
        profile=profile,
        provider_id=profile.provider_id,
        model_name=profile.model_name or newsletter.model_name,
        api_key_id=profile.api_key_id,
        binding_mode=profile.api_key_binding_mode,
    )


def resolve_delivery_profile(db: DbSession, newsletter: Newsletter) -> ResolvedDeliveryProfile:
    profile = None
    if newsletter.delivery_profile_id is not None:
        profile = db.scalar(
            select(DeliveryProfile).where(DeliveryProfile.id == newsletter.delivery_profile_id)
        )

    if profile is None:
        return ResolvedDeliveryProfile(
            profile=None,
            api_key_id=newsletter.resend_api_key_id,
            from_email=None,
            binding_mode=None,
        )

    return ResolvedDeliveryProfile(
        profile=profile,
        api_key_id=profile.api_key_id,
        from_email=profile.from_email,
        binding_mode=profile.api_key_binding_mode,
    )
