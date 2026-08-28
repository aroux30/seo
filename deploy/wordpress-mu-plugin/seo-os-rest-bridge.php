<?php
/**
 * Plugin Name: AI SEO OS — REST Bridge for Rank Math
 * Description: Exposes Rank Math SEO post meta (focus keyword, description, title) through the
 *              WordPress REST API so the AI SEO OS platform can set them when publishing articles.
 *              Drop this file into wp-content/mu-plugins/ — it activates automatically.
 * Version:     1.0.0
 * Author:      AI SEO OS
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action( 'init', 'seo_os_register_rankmath_rest_meta' );
/**
 * Register Rank Math's postmeta keys with show_in_rest so they can be read and
 * written over /wp-json/wp/v2/posts/{id} under the `meta` object.
 *
 * Rank Math stores its SEO data in exactly these postmeta keys but (as of
 * current versions) does not register them for the REST API, which silently
 * drops REST writes. Registering them here bridges that gap. When Rank Math is
 * present it still owns rendering; this only opens the storage to REST.
 */
function seo_os_register_rankmath_rest_meta() {
	$post_types = apply_filters( 'seo_os_bridge_post_types', array( 'post', 'page' ) );

	$meta_keys = array(
		'rank_math_focus_keyword' => 'text',     // Focus Keyword box in Rank Math
		'rank_math_description'   => 'text',     // SEO Description box
		'rank_math_title'         => 'text',     // SEO Title box
	);

	foreach ( $post_types as $post_type ) {
		foreach ( $meta_keys as $meta_key => $type ) {
			register_post_meta(
				$post_type,
				$meta_key,
				array(
					'type'          => 'string',
					'single'        => true,
					'show_in_rest'  => true,
					'default'       => '',
					'auth_callback' => function () {
						// Application-password REST requests authenticate as the
						// linked WP user, so normal edit capability is enough.
						return current_user_can( 'edit_posts' );
					},
				)
			);
		}
	}
}
